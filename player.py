#!/usr/bin/env python3

import os
import sys
import time
import argparse
from pythonosc import dispatcher
from pythonosc import osc_server
import threading
import subprocess
import signal
import logging
from pathlib import Path

# Set up logging
def setup_logging(log_file=None):
    """Set up logging configuration"""
    log_dir = Path.home() / "logs"
    log_dir.mkdir(exist_ok=True)
    
    if log_file is None:
        log_file = log_dir / "video_player.log"
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("VideoPlayer")

logger = setup_logging()

# Default configuration
DEFAULT_OSC_IP = "0.0.0.0"  # Listen on all interfaces
DEFAULT_OSC_PORT = 8000
DEFAULT_VIDEO_DIRECTORY = str(Path.home() / "Videos")  # Default to user's Videos directory
VLC_PATH = "/usr/bin/cvlc"  # Path to command-line VLC

# Environment variables for VLC
VLC_ENV = os.environ.copy()
VLC_ENV["DISPLAY"] = ":0"  # Set display to :0 for HDMI output
# Try to find X authority file
xauth_path = Path.home() / ".Xauthority"
if xauth_path.exists():
    VLC_ENV["XAUTHORITY"] = str(xauth_path)

# Global variables
current_process = None
is_running = True
current_volume = 80  # Default volume level (0-100)
volume_step = 5      # How much to change volume each time
video_directory = DEFAULT_VIDEO_DIRECTORY

def get_current_mixer_controls():
    """Get the available mixer controls to determine which one to use for volume"""
    try:
        result = subprocess.run(['amixer', 'scontrols'], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        controls = result.stdout.strip().split('\n')
        logger.info(f"Available mixer controls: {controls}")
        return controls
    except Exception as e:
        logger.error(f"Error getting mixer controls: {e}")
        return []

def get_volume_control():
    """Determine which volume control to use"""
    controls = get_current_mixer_controls()
    
    # Try to find the appropriate control
    for control in controls:
        if "'Master'" in control:
            return "Master"
        elif "'PCM'" in control:
            return "PCM"
        elif "'Speaker'" in control:
            return "Speaker"
    
    # Default to PCM if no known control is found
    logger.warning("Could not identify volume control, defaulting to PCM")
    return "PCM"

# Get the volume control to use
VOLUME_CONTROL = get_volume_control()
logger.info(f"Using volume control: {VOLUME_CONTROL}")

def set_system_volume(volume_percent):
    """Set the system volume using amixer"""
    try:
        # Ensure volume is within valid range
        volume_percent = max(0, min(100, volume_percent))
        
        # Run amixer command to set volume
        cmd = ['amixer', 'set', VOLUME_CONTROL, f'{volume_percent}%']
        logger.info(f"Running volume command: {' '.join(cmd)}")
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode == 0:
            logger.info(f"Volume set to {volume_percent}%")
            return True
        else:
            logger.error(f"Error setting volume: {result.stderr}")
            return False
    except Exception as e:
        logger.error(f"Exception while setting volume: {e}")
        return False

def get_system_volume():
    """Get the current system volume"""
    try:
        result = subprocess.run(['amixer', 'get', VOLUME_CONTROL], 
                               stdout=subprocess.PIPE, 
                               stderr=subprocess.PIPE, 
                               text=True)
        
        # Parse the output to get the volume percentage
        output = result.stdout
        if "%" in output:
            volume_str = output[output.find("[")+1:output.find("%")]
            return int(volume_str)
        
        logger.warning(f"Could not parse volume from output: {output}")
        return 80  # Default if we can't determine
    except Exception as e:
        logger.error(f"Error getting system volume: {e}")
        return 80  # Default if error

def play_video(video_filename):
    """Play a video file using VLC"""
    global current_process, current_volume
    
    # Kill any existing video playback
    stop_video()
    
    # Full path to the video
    video_path = Path(video_directory) / video_filename
    
    # Check if file exists
    if not video_path.is_file():
        logger.error(f"Video file not found: {video_path}")
        return
    
    logger.info(f"Playing video: {video_path}")
    
    # Get the current system volume
    current_volume = get_system_volume()
    
    # First hide the mouse cursor
    try:
        subprocess.run(["unclutter", "-display", ":0", "-idle", "0.1", "-root"], 
                      env=VLC_ENV, check=False)
    except Exception as e:
        logger.warning(f"Could not hide cursor: {e}")
    
    try:
        # Start VLC with appropriate settings for Raspberry Pi 5
        current_process = subprocess.Popen([
            VLC_PATH,
            "--fullscreen",            # Full screen mode
            "--no-video-title-show",   # Don't show video title
            "--loop",                  # Loop VLC when playback ends
            "--no-osd",                # No on-screen display
            "--video-on-top",          # Keep video on top
            "--key-quit", "Ctrl+c",    # Change quit key to reduce accidental exits
            "--mouse-hide-timeout=1",  # Hide mouse cursor quickly
            "--vout", "x11",           # Use X11 video output for Pi 5
            video_path
        ], env=VLC_ENV, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        logger.debug(f"VLC process started with PID: {current_process.pid}")
        
        # Start a thread to monitor the VLC output
        threading.Thread(target=monitor_vlc_output, args=(current_process,), daemon=True).start()
    except Exception as e:
        logger.error(f"Error starting VLC: {e}")

def volume_up():
    """Increase volume"""
    global current_volume
    
    # Get current system volume
    current_volume = get_system_volume()
    
    # Increase volume by step amount
    new_volume = min(100, current_volume + volume_step)
    logger.info(f"Increasing volume from {current_volume}% to {new_volume}%")
    
    if set_system_volume(new_volume):
        current_volume = new_volume
        return True
    
    return False

def volume_down():
    """Decrease volume"""
    global current_volume
    
    # Get current system volume
    current_volume = get_system_volume()
    
    # Decrease volume by step amount
    new_volume = max(0, current_volume - volume_step)
    logger.info(f"Decreasing volume from {current_volume}% to {new_volume}%")
    
    if set_system_volume(new_volume):
        current_volume = new_volume
        return True
    
    return False

def volume_set(value):
    """Set volume to a specific value (0-100)"""
    global current_volume
    
    # Validate volume value
    try:
        value = int(value)
        if value < 0 or value > 100:
            logger.warning(f"Invalid volume level: {value}. Must be between 0-100")
            return False
    except ValueError:
        logger.warning(f"Invalid volume value: {value}")
        return False
    
    logger.info(f"Setting volume to {value}%")
    
    if set_system_volume(value):
        current_volume = value
        return True
    
    return False

def monitor_vlc_output(process):
    """Monitor VLC output for errors"""
    while process.poll() is None:
        output = process.stdout.readline()
        if output:
            logger.debug(f"VLC output: {output.decode().strip()}")
        
        error = process.stderr.readline()
        if error:
            logger.warning(f"VLC error: {error.decode().strip()}")
        
        time.sleep(0.1)
    
    return_code = process.poll()
    logger.info(f"VLC process ended with return code: {return_code}")

def create_black_screen():
    """Create a simple black screen using feh (image viewer)"""
    try:
        # Create a black image file in temp directory
        temp_dir = Path.home() / ".cache" / "piosc"
        temp_dir.mkdir(parents=True, exist_ok=True)
        black_image_path = temp_dir / "black.png"
        
        if not black_image_path.exists():
            logger.info("Creating black image")
            with open(black_image_path, "wb") as f:
                # Create a simple 1x1 black PNG
                f.write(bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010100000000376ef9240000001049444154789c6260000000000000000000ffff03000006000557bfabd40000000049454e44ae426082"))
        
        # Use feh to display the black image fullscreen
        return subprocess.Popen([
            "feh", 
            "--fullscreen",
            "--hide-pointer",
            str(black_image_path)
        ], env=VLC_ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        logger.error(f"Error creating black screen with feh: {e}")
        return None

def stop_video():
    """Stop any currently playing video and show black screen"""
    global current_process
    
    # Kill any existing video playback
    if current_process and current_process.poll() is None:
        logger.info(f"Stopping video playback (PID: {current_process.pid})")
        current_process.terminate()
        # Give it a moment to terminate gracefully
        time.sleep(0.5)
        # Force kill if still running
        if current_process.poll() is None:
            logger.warning(f"Process did not terminate gracefully, forcing kill")
            current_process.kill()
        current_process = None
    
    # Display black screen using feh (image viewer) - simpler and more reliable
    try:
        # Make sure feh is installed
        subprocess.run(["which", "feh"], check=True)
        current_process = create_black_screen()
        if current_process:
            logger.info(f"Black screen displayed with PID: {current_process.pid}")
        else:
            logger.error("Failed to display black screen")
    except subprocess.CalledProcessError:
        logger.warning("feh not found. Installing...")
        try:
            subprocess.run(["sudo", "apt-get", "update", "-qq"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", "feh", "unclutter"], check=True)
            logger.info("feh installed")
            current_process = create_black_screen()
        except Exception as e:
            logger.error(f"Failed to install feh: {e}")
            # Fallback to a simpler approach if feh fails
            try:
                logger.info("Trying simpler blank screen approach")
                current_process = subprocess.Popen([
                    "xset", "s", "blank", "s", "on"
                ], env=VLC_ENV, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception as e2:
                logger.error(f"All blank screen methods failed: {e2}")

def handle_osc_message(address, *args):
    """Generic OSC message handler that logs all incoming messages"""
    logger.info(f"Received OSC message at address: {address}")
    logger.info(f"Arguments: {args}")
    
    # Extract the command from the address
    command = address.lstrip('/')
    
    if command == "play" and len(args) > 0:
        video_filename = str(args[0])
        logger.info(f"Playing video: {video_filename}")
        play_video(video_filename)
    elif command == "stop":
        logger.info("Stopping video")
        stop_video()
    elif command == "volume_up":
        logger.info("Increasing volume")
        volume_up()
    elif command == "volume_down":
        logger.info("Decreasing volume")
        volume_down()
    elif command == "volume_set" and len(args) > 0:
        try:
            vol_level = int(args[0])
            logger.info(f"Setting volume to: {vol_level}")
            volume_set(vol_level)
        except (ValueError, TypeError):
            logger.warning(f"Invalid volume value: {args}")
    else:
        logger.warning(f"Unknown command: {command} with args: {args}")

def main():
    parser = argparse.ArgumentParser(description='Video Player for Theatre Show')
    parser.add_argument('--ip', default=DEFAULT_OSC_IP, help='OSC server IP')
    parser.add_argument('--port', type=int, default=DEFAULT_OSC_PORT, help='OSC server port')
    parser.add_argument('--video-dir', default=DEFAULT_VIDEO_DIRECTORY, help='Directory containing video files')
    parser.add_argument('--volume-step', type=int, default=5, help='Volume change step (1-20)')
    parser.add_argument('--log-file', help='Path to log file')
    args = parser.parse_args()
    
    # Set video directory from command line
    global video_directory, volume_step
    video_directory = args.video_dir
    
    # Ensure video directory exists
    if not Path(video_directory).exists():
        logger.error(f"Video directory does not exist: {video_directory}")
        sys.exit(1)
    
    # Set volume step from command line if provided
    if args.volume_step:
        volume_step = max(1, min(20, args.volume_step))
    
    # Setup logging with custom file if provided
    if args.log_file:
        global logger
        logger = setup_logging(args.log_file)
    
    logger.info(f"Starting Video Player on {args.ip}:{args.port}")
    logger.info(f"Video directory: {video_directory}")
    logger.info(f"Volume step: {volume_step}")
    
    # Disable screen blanking/screensaver
    try:
        subprocess.run(["xset", "-dpms"], env=VLC_ENV, check=False)
        subprocess.run(["xset", "s", "off"], env=VLC_ENV, check=False)
        subprocess.run(["xset", "s", "noblank"], env=VLC_ENV, check=False)
        logger.info("Disabled screen blanking/screensaver")
    except Exception as e:
        logger.warning(f"Could not disable screen blanking: {e}")
    
    # Set up OSC dispatcher with a generic handler
    dispatcher_obj = dispatcher.Dispatcher()
    
    # Map the generic handler to all OSC addresses
    dispatcher_obj.map("/*", handle_osc_message)
    
    # Start OSC server
    try:
        server = osc_server.ThreadingOSCUDPServer((args.ip, args.port), dispatcher_obj)
        server_thread = threading.Thread(target=server.serve_forever)
        server_thread.daemon = True
        
        logger.info(f"OSC server started on {args.ip}:{args.port}")
        server_thread.start()
    except Exception as e:
        logger.error(f"Error starting OSC server: {e}")
        sys.exit(1)
    
    # Make sure required packages are installed
    try:
        # Check if feh is available
        subprocess.run(["which", "feh"], check=True)
    except subprocess.CalledProcessError:
        logger.warning("feh not found. Installing required packages...")
        try:
            subprocess.run(["sudo", "apt-get", "update", "-qq"], check=True)
            subprocess.run(["sudo", "apt-get", "install", "-y", "feh", "unclutter"], check=True)
            logger.info("Required packages installed")
        except Exception as e:
            logger.error(f"Failed to install required packages: {e}")
    
    # Show blank screen at startup
    stop_video()
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        global is_running
        logger.info(f"Received signal {sig}, shutting down...")
        stop_video()
        is_running = False
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Keep main thread alive
    try:
        logger.info("Video Player is running. Press Ctrl+C to exit.")
        while is_running:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
        stop_video()
        sys.exit(0)

if __name__ == "__main__":
    main()

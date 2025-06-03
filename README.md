# PiOSC - Raspberry Pi Video Player with OSC Control

A Python-based video player designed for Raspberry Pi 5 that can be controlled remotely via OSC (Open Sound Control) messages. Perfect for theatre shows, installations, and any application requiring remote video playback control.

## Features

- 🎬 Full-screen video playback using VLC
- 🎛️ OSC control for remote operation
- 🔊 System volume control via OSC
- 🖥️ HDMI output support for Raspberry Pi 5
- 📱 Compatible with TouchOSC and other OSC controllers
- 🔄 Automatic looping and seamless playback
- 📝 Comprehensive logging
- ⚫ Black screen display when no video is playing

## Requirements

### Hardware
- Raspberry Pi 5 (tested) or Raspberry Pi 4
- HDMI display/projector
- Network connection (WiFi or Ethernet)

### Software
- Raspberry Pi OS (Bookworm recommended)
- Python 3.7+
- VLC media player
- X11 desktop environment

## Installation

### 1. Update your Raspberry Pi
```bash
sudo apt update && sudo apt upgrade -y
```

### 2. Install required system packages
```bash
sudo apt install -y python3-pip vlc feh unclutter
```

### 3. Install Python dependencies
```bash
pip3 install python-osc
```

### 4. Clone this repository
```bash
git clone https://github.com/smeg9/PiOSC.git
cd PiOSC
```

### 5. Make the script executable
```bash
chmod +x player.py
```

## Configuration

### Video Directory
By default, the player looks for videos in `~/Videos/`. You can specify a different directory using the `--video-dir` argument:

```bash
python3 player.py --video-dir /path/to/your/videos
```

### OSC Settings
- **Default IP**: `0.0.0.0` (listens on all network interfaces)
- **Default Port**: `8000`
- **Protocol**: UDP

To use different settings:
```bash
python3 player.py --ip 192.168.1.100 --port 9000
```

## Usage

### Starting the Player
```bash
python3 player.py
```

With custom options:
```bash
python3 player.py --ip 0.0.0.0 --port 8000 --video-dir ~/MyVideos --volume-step 10
```

### Command Line Arguments
- `--ip`: OSC server IP address (default: 0.0.0.0)
- `--port`: OSC server port (default: 8000)
- `--video-dir`: Directory containing video files (default: ~/Videos)
- `--volume-step`: Volume change increment 1-20 (default: 5)
- `--log-file`: Custom log file path

## OSC Commands

All OSC commands are sent as UDP messages to the configured IP and port.

### Video Control

#### Play Video
- **Address**: `/play`
- **Arguments**: `filename` (string)
- **Example**: `/play "myvideo.mp4"`

Plays the specified video file from the video directory. Supports most video formats that VLC can handle (MP4, AVI, MOV, MKV, etc.).

#### Stop Video
- **Address**: `/stop`
- **Arguments**: None
- **Example**: `/stop`

Stops the currently playing video and displays a black screen.

### Volume Control

#### Volume Up
- **Address**: `/volume_up`
- **Arguments**: None
- **Example**: `/volume_up`

Increases system volume by the configured step amount (default: 5%).

#### Volume Down
- **Address**: `/volume_down`
- **Arguments**: None
- **Example**: `/volume_down`

Decreases system volume by the configured step amount (default: 5%).

#### Set Volume
- **Address**: `/volume_set`
- **Arguments**: `level` (integer, 0-100)
- **Example**: `/volume_set 75`

Sets the system volume to a specific level (0-100%).

## TouchOSC Integration

PiOSC works great with TouchOSC. Here's a sample TouchOSC layout configuration:

### Simple Control Panel
1. **Play Button**: Send `/play` with a text field for filename
2. **Stop Button**: Send `/stop`
3. **Volume Fader**: Send `/volume_set` with fader value (0-100)
4. **Volume Up/Down**: Send `/volume_up` and `/volume_down`

### Example TouchOSC Messages
```
Button 1: /play "intro.mp4"
Button 2: /play "main_show.mp4"
Button 3: /stop
Fader 1: /volume_set [fader_value]
```

## Network Setup

### Finding Your Pi's IP Address
```bash
hostname -I
```

### Testing OSC Connection
You can test the connection using various OSC tools or with Python:

```python
from pythonosc import udp_client

client = udp_client.SimpleUDPClient("192.168.1.100", 8000)
client.send_message("/play", "test.mp4")
```

## Troubleshooting

### Video Won't Play
- Check that the video file exists in the specified directory
- Ensure the video format is supported by VLC
- Check the log file for error messages: `~/logs/video_player.log`

### No Audio
- Check HDMI audio settings: `sudo raspi-config` → Advanced Options → Audio → Force HDMI
- Verify volume levels: `alsamixer`
- Check audio device: `aplay -l`

### Display Issues
- Ensure X11 is running: `echo $DISPLAY` should return `:0`
- Check HDMI connection and display settings
- Try: `sudo raspi-config` → Advanced Options → Resolution

### OSC Connection Issues
- Check firewall settings: `sudo ufw status`
- Verify network connectivity: `ping [controller-ip]`
- Test with a simple OSC tool first

### Performance Issues
- Use hardware-accelerated video formats (H.264)
- Ensure adequate power supply (5V 3A for Pi 5)
- Check CPU/GPU memory split: `sudo raspi-config` → Advanced Options → Memory Split (set to 128 or 256)

## Autostart Setup

To start the player automatically on boot:

### 1. Create a systemd service
```bash
sudo nano /etc/systemd/system/piosc.service
```

### 2. Add the following content:
```ini
[Unit]
Description=PiOSC Video Player
After=graphical-session.target

[Service]
Type=simple
User=pi
Environment=DISPLAY=:0
WorkingDirectory=/home/pi/PiOSC
ExecStart=/usr/bin/python3 /home/pi/PiOSC/player.py --video-dir /home/pi/Videos
Restart=always
RestartSec=5

[Install]
WantedBy=graphical-session.target
```

### 3. Enable and start the service
```bash
sudo systemctl enable piosc.service
sudo systemctl start piosc.service
```

## File Formats

Supported video formats include:
- MP4 (H.264/H.265)
- AVI
- MOV
- MKV
- WMV
- FLV
- And many others supported by VLC

For best performance on Raspberry Pi, use:
- **Codec**: H.264
- **Container**: MP4
- **Resolution**: 1920x1080 or lower
- **Bitrate**: 10 Mbps or lower

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

If you encounter issues:
1. Check the troubleshooting section above
2. Review the log files in `~/logs/`
3. Open an issue on GitHub with relevant log output

## Acknowledgments

- Built with [python-osc](https://github.com/attwad/python-osc)
- Uses VLC media player for robust video playback
- Designed for theatre and live performance applications
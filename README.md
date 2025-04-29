# Live Transcribe

> **⚠️ WARNING ⚠️**  
> The transcription quality is kind of terrible sometimes... but we can blame OpenAI for that! 🤷‍♂️

![Python](https://img.shields.io/badge/Python-3.7+-blue)

A real-time audio transcription tool that converts speech to text using OpenAI's Whisper model.

## 📋 Overview

Live Transcribe listens to your audio input and provides real-time transcriptions. It's perfect for:
- Watching streams or videos in different languages but auto caption is not cutting it

## ⚙️ Setup

### Prerequisites
- Python 3.7 or higher
- An OpenAI API key
- Audio input device (microphone or virtual audio cable)

### Installation

1. **Clone the repository**
   ```
   git clone https://github.com/dev-idkwhoami/live-transcribe.git
   cd live-transcribe
   ```

2. **Set up a virtual environment (recommended)**
   ```
   python -m venv .venv
   # Windows
   .venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   ```

3. **Install dependencies**
   ```
   pip install openai python-dotenv pyaudio
   ```

4. **Configure your environment**
   - Run the application once to create the initial files
   - Add your OpenAI API key to the generated `.env` file:
     ```
     OPENAI_API_KEY=your_api_key_here
     ```
   - The `config.json` file will be created automatically

## 🚀 Usage

1. **Start the application**
   ```
   python live_transcribe.py
   ```

2. **Select an audio input device** when prompted

3. **Begin speaking** and see your words transcribed in real-time

## ⚠️ Notes

- Transcription consumes OpenAI API credits
- For best results, use a high-quality microphone
- To capture system audio, use a virtual audio cable like VB-Cable

## 📜 License

MIT License

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
# Inventory Management System

A cloud-based inventory management system with product scanning, AI-powered insights, and real-time tracking.

## Features

- Product inventory management
- Image-based product scanning using Google Cloud Vision
- AI-powered inventory insights and reports
- Usage history tracking
- Low stock alerts
- User authentication

## Deployment Instructions

### Prerequisites

1. Create a GitHub account if you don't have one
2. Create a Streamlit Cloud account
3. Set up Google Cloud Vision API
4. Set up OpenAI API

### Steps to Deploy

1. **Prepare Your Code**:
   - Remove sensitive information from the code
   - Create a `.env` file with your API keys (don't commit this to GitHub)
   - Ensure all dependencies are in `requirements.txt`

2. **Push to GitHub**:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <your-github-repo-url>
   git push -u origin main
   ```

3. **Deploy to Streamlit Cloud**:
   - Go to [Streamlit Cloud](https://streamlit.io/cloud)
   - Click "New app"
   - Connect your GitHub repository
   - Select the main branch and app.py file
   - Add your secrets in the "Advanced settings" section

### Environment Variables

Create a `.env` file with the following variables:
```
OPENAI_API_KEY=your_openai_api_key
GOOGLE_APPLICATION_CREDENTIALS=credentials/google-credentials.json
```

### Secrets in Streamlit Cloud

Add these secrets in Streamlit Cloud:
- OPENAI_API_KEY
- GOOGLE_APPLICATION_CREDENTIALS (as a file)

## Local Development

1. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   streamlit run app.py
   ```

## Security Notes

- Never commit API keys or credentials to GitHub
- Use environment variables for sensitive information
- Keep your `.env` file in `.gitignore`
- Regularly rotate your API keys

## Project Structure

```
inventory-tracking/
├── app.py                 # Main application file
├── database.py           # Database operations
├── vision_utils.py       # Image processing utilities
├── chatbot.py            # AI chat functionality
├── requirements.txt      # Project dependencies
├── .env                  # Environment variables (not in git)
├── .gitignore           # Git ignore file
└── README.md            # Project documentation
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details. 
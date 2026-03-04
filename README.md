# BS Finance - Client Management System

A Flask-based client management system with document uploads and WhatsApp integration.

## Windows Setup Instructions

### Option 1: Using the batch script (Recommended)
1. Make sure you have Python installed (Python 3.7 or higher recommended)
2. Double-click `run.bat` to start the application
3. The script will:
   - Create a virtual environment
   - Install all dependencies
   - Start the Flask server

### Option 2: Manual Setup
1. Install Python from https://www.python.org/downloads/
2. Open Command Prompt in this folder
3. Create a virtual environment:
   
```
   python -m venv venv
   
```
4. Activate the virtual environment:
   
```
   venv\Scripts\activate.bat
   
```
5. Install dependencies:
   
```
   pip install -r requirements.txt
   
```
6. Run the application:
   
```
   python app.py
   
```

## Accessing the Application

Once running, open your browser and go to:
- http://127.0.0.1:5000

## Features

- Client Management (Add, Edit, Delete, Search)
- Document Upload and Storage
- WhatsApp Message Templates
- Quick Upload functionality
- Storage Information

## Stopping the Server

Press Ctrl+C in the Command Prompt window to stop the server.

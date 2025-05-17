# FastAPI and NiceGUI Application

This project is a web application built using FastAPI for the backend API and NiceGUI for the user interface.

## Project Structure

```
epaper-nice
├── app
│   ├── api
│   │   ├── __init__.py
│   │   └── endpoints.py
│   ├── ui
│   │   ├── __init__.py
│   │   └── endpoints.py
│   ├── core
│   │   └── buissneslogic.py
│   ├── models
│   │   └── models.py
│   └── config.py
│   └── main.py
├── data
│   └── example.json
├── README.md
├── requirements.txt
└── docker-compose.yml
```

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/username/repositoryname.git
   cd repositoryname
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. Install the required packages:
   ```
   pip install -r requirements.txt
   ```

## Usage

1. Start the application:
   ```
   uvicorn app.main:app --reload
   ```

2. Access the API at `http://127.0.0.1:8000/api` and the NiceGUI interface at `http://127.0.0.1:8000/ui`.

## Features

- Manage JSON files in the `data` directory.
- User-friendly interface for selecting and editing JSON files.

## Contributing

Feel free to submit issues or pull requests for improvements and bug fixes.

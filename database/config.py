import os

# Default connection parameters – you can override them with environment variables.
# Example: export DB_HOST=localhost, DB_PORT=5432, DB_NAME=college_notice, DB_USER=postgres, DB_PASSWORD=postgres
DB_HOST = os.getenv('DB_HOST', 'localhost')
DB_PORT = int(os.getenv('DB_PORT', '5432'))
DB_NAME = os.getenv('DB_NAME', 'college_notice')
DB_USER = os.getenv('DB_USER', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'postgres')

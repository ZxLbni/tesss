# Use the official Python image.
FROM python:3.9

# Set the working directory.
WORKDIR /app

# Copy requirements.txt and install dependencies.
COPY requirements.txt requirements.txt
RUN pip install -r requirements.txt

# Copy the rest of the application code.
COPY . .

# Start the bot
CMD ["python", "bot.py"]

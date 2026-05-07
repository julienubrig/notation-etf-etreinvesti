📘 ETF Data Ingestion Pipeline
This project implements a data ingestion pipeline for Exchange‑Traded Funds (ETFs).
It scrapes public financial sources, cleans the extracted data, and loads the results into a PostgreSQL database for analysis and dashboarding.

🔍 What the pipeline does
Scrapes ETF metadata and market information from multiple public websites
Cleans and normalizes raw HTML data
Handles batching, rate limiting, and retry logic to avoid blocking
Stores structured data in a PostgreSQL database
Can be scheduled for periodic updates (Windows Task Scheduler)

🧱 Architecture
Code
├── main.py          → Orchestrates the full pipeline
├── get_data.py      → Web scraping logic (requests, parsing)
├── cleaning.py      → Data cleaning and formatting
└── update_db.py     → Database insertion and updates

🛠 Technologies
Python
PostgreSQL
Requests
BeautifulSoup4
Pandas
Python-dotenv

🔐 Environment configuration
Create a .env file in the project root (not included in the repository):

Code
DB_HOST=localhost
DB_PORT=5432
DB_NAME=etf
DB_USER=postgres
DB_PASSWORD=your_password
This file is ignored for security reasons.

▶️ Running the pipeline
Install dependencies:
pip install -r requirements.txt

Run the main pipeline:
python main.py

The script will scrape ETF data, clean it, and update the SQL database.

📁 Repository notes
All .xlsx files used as local inputs are intentionally excluded.
.env is excluded for security.

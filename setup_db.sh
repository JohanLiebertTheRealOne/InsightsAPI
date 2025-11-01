#!/usr/bin/env bash
# Database Setup Script for InsightFinance API
# ============================================
#
# This script helps set up PostgreSQL and Redis for local development.
# Run this script to create the database and user.

set -e

echo "🚀 Setting up InsightFinance API database..."

# Database configuration
DB_NAME="insightfinance"
DB_USER="postgres"
DB_PASSWORD="postgres"
DB_HOST="localhost"
DB_PORT="5432"

# Check if PostgreSQL is running
if ! pg_isready -h $DB_HOST -p $DB_PORT > /dev/null 2>&1; then
    echo "❌ PostgreSQL is not running. Please start PostgreSQL first."
    echo "   On Ubuntu/Debian: sudo systemctl start postgresql"
    echo "   On macOS with Homebrew: brew services start postgresql"
    echo "   On Docker: docker run -d --name postgres -e POSTGRES_PASSWORD=postgres -p 5432:5432 postgres:13"
    exit 1
fi

echo "✅ PostgreSQL is running"

# Create database if it doesn't exist
echo "📊 Creating database '$DB_NAME'..."
createdb -h $DB_HOST -p $DB_PORT -U $DB_USER $DB_NAME 2>/dev/null || echo "Database already exists"

echo "✅ Database '$DB_NAME' is ready"

# Run migration
echo "🔄 Running database migration..."
python3 migrate.py

echo "🎉 Database setup completed!"
echo ""
echo "Next steps:"
echo "1. Create a .env file with your configuration"
echo "2. Install dependencies: pip install -r requirements.txt"
echo "3. Start Redis: redis-server"
echo "4. Run the API: python3 -m uvicorn app.main:app --reload"
# InsightFinance API

Modern financial API with FastAPI, PostgreSQL, Redis, and smart analytics.

## Quickstart

### Prerequisites
- Python 3.8+
- PostgreSQL 12+
- Redis 6+

### 1. Clone and Setup
```bash
git clone <your-repo>
cd InsightsAPI
pip install -r requirements.txt
```

### 2. Database Setup
```bash
# Option A: Use the setup script (Linux/macOS)
./setup_db.sh

# Option B: Manual setup
createdb insightfinance
python migrate.py
```

### 3. Environment Configuration
Create `.env` file:
```env
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO
LOG_FILE=insightfinance.log
SECRET_KEY=change-this-in-production
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/insightfinance
REDIS_URL=redis://localhost:6379
ALPHA_VANTAGE_API_KEY=demo
CORS_ORIGINS=["*"]
CORS_CREDENTIALS=true
CORS_METHODS=["*"]
CORS_HEADERS=["*"]
```

### 4. Start Services
```bash
# Start Redis (in separate terminal)
redis-server

# Start the API
uvicorn app.main:app --reload
```

### 5. Access Documentation
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- Health Check: http://localhost:8000/health

## API Endpoints [WIP]

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/token` - Login and get JWT token

### Market Data
- `GET /prices/{symbol}` - Get current price and history (requires auth)

### Technical Analysis
- `GET /signals/{symbol}` - Get BUY/SELL/HOLD signal (requires auth)

### Portfolio Analytics
- `GET /portfolio/{user_id}` - Get portfolio metrics (requires auth)

### Asset Screening
- `GET /screener?strategy=momentum` - Get top assets by strategy (requires auth)

## Example Usage

```bash
# Register a user
curl -X POST "http://localhost:8000/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'

# Login and get token
curl -X POST "http://localhost:8000/auth/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=user@example.com&password=password123"

# Get BTC price (replace TOKEN with actual JWT)
curl -X GET "http://localhost:8000/prices/BTCUSD" \
  -H "Authorization: Bearer TOKEN"

# Get BTC signal
curl -X GET "http://localhost:8000/signals/BTCUSD" \
  -H "Authorization: Bearer TOKEN"
```

## Deploy to Render/Railway

### Environment Variables
Set these in your deployment platform:
- `ENVIRONMENT=production`
- `SECRET_KEY=<strong-random-key>`
- `DATABASE_URL=<postgresql-connection-string>`
- `REDIS_URL=<redis-connection-string>`
- `ALPHA_VANTAGE_API_KEY=<your-api-key>`
- `CORS_ORIGINS=["https://yourdomain.com"]`

### Build Command
```bash
pip install -r requirements.txt && python migrate.py                        
```

### Start Command
```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Architecture

- **FastAPI**: Modern Python web framework with automatic OpenAPI docs
- **PostgreSQL**: Primary database with SQLAlchemy ORM
- **Redis**: Caching layer for API responses and computed indicators
- **JWT**: Stateless authentication
- **Alpha Vantage**: Primary market data source with fallbacks

## Future Enhancements
- Stripe integration for paid plans
- WebSockets for real-time updates
- AI-powered market insights
- Multi-language support
- Admin dashboard (Next.js + Tailwind)
 
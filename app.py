"""
NSE India Real-Time Data Scraper Backend
This Flask server scrapes live NSE data and provides it via API
Deploy on: Render.com, Railway.app, or Heroku (all have free tiers)
"""

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime
import logging

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend access

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# NSE Headers to mimic browser
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
    'Referer': 'https://www.nseindia.com/'
}

# Session for maintaining cookies
session = requests.Session()
session.headers.update(HEADERS)

# Cache for storing data (reduce NSE load)
cache = {
    'data': None,
    'timestamp': 0,
    'ttl': 60  # Cache for 60 seconds
}

def init_nse_session():
    """Initialize NSE session by visiting homepage first"""
    try:
        session.get('https://www.nseindia.com', headers=HEADERS, timeout=10)
        time.sleep(1)
        return True
    except Exception as e:
        logger.error(f"Failed to initialize NSE session: {e}")
        return False

def fetch_nse_stock_data(symbol):
    """Fetch real-time data for a single stock from NSE"""
    try:
        url = f'https://www.nseindia.com/api/quote-equity?symbol={symbol}'
        response = session.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract relevant data
            price_info = data.get('priceInfo', {})
            price_band = data.get('metadata', {})
            
            return {
                'symbol': symbol,
                'name': price_band.get('companyName', symbol),
                'price': price_info.get('lastPrice', 0),
                'change': price_info.get('change', 0),
                'pChange': price_info.get('pChange', 0),
                'previousClose': price_info.get('previousClose', 0),
                'open': price_info.get('open', 0),
                'dayHigh': price_info.get('intraDayHighLow', {}).get('max', 0),
                'dayLow': price_info.get('intraDayHighLow', {}).get('min', 0),
                'volume': price_info.get('totalTradedVolume', 0),
                'value': price_info.get('totalTradedValue', 0),
                'lastUpdateTime': price_info.get('lastUpdateTime', ''),
                'timestamp': datetime.now().isoformat()
            }
        else:
            logger.error(f"Failed to fetch {symbol}: Status {response.status_code}")
            return None
            
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None

def fetch_nse_indices():
    """Fetch Nifty 50 and other indices"""
    try:
        url = 'https://www.nseindia.com/api/allIndices'
        response = session.get(url, headers=HEADERS, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            indices = {}
            
            for item in data.get('data', []):
                index_name = item.get('index', '')
                if index_name in ['NIFTY 50', 'NIFTY BANK', 'NIFTY IT', 'NIFTY MIDCAP 100']:
                    indices[index_name] = {
                        'value': item.get('last', 0),
                        'change': item.get('variation', 0),
                        'pChange': item.get('percentChange', 0),
                        'open': item.get('open', 0),
                        'high': item.get('high', 0),
                        'low': item.get('low', 0)
                    }
            
            return indices
        else:
            logger.error(f"Failed to fetch indices: Status {response.status_code}")
            return {}
            
    except Exception as e:
        logger.error(f"Error fetching indices: {e}")
        return {}

def fetch_top_gainers_losers():
    """Fetch top gainers and losers from NSE"""
    try:
        # Top gainers
        gainers_url = 'https://www.nseindia.com/api/live-analysis-variations?index=gainers'
        gainers_response = session.get(gainers_url, headers=HEADERS, timeout=10)
        
        # Top losers
        losers_url = 'https://www.nseindia.com/api/live-analysis-variations?index=losers'
        losers_response = session.get(losers_url, headers=HEADERS, timeout=10)
        
        result = {
            'gainers': [],
            'losers': []
        }
        
        if gainers_response.status_code == 200:
            gainers_data = gainers_response.json()
            for item in gainers_data.get('NIFTY', {}).get('data', [])[:10]:
                result['gainers'].append({
                    'symbol': item.get('symbol', ''),
                    'name': item.get('meta', {}).get('companyName', ''),
                    'price': item.get('lastPrice', 0),
                    'change': item.get('change', 0),
                    'pChange': item.get('pChange', 0)
                })
        
        if losers_response.status_code == 200:
            losers_data = losers_response.json()
            for item in losers_data.get('NIFTY', {}).get('data', [])[:10]:
                result['losers'].append({
                    'symbol': item.get('symbol', ''),
                    'name': item.get('meta', {}).get('companyName', ''),
                    'price': item.get('lastPrice', 0),
                    'change': item.get('change', 0),
                    'pChange': item.get('pChange', 0)
                })
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching gainers/losers: {e}")
        return {'gainers': [], 'losers': []}

# Define top NSE stocks to track
TOP_STOCKS = [
    'RELIANCE', 'TCS', 'HDFCBANK', 'INFY', 'ICICIBANK',
    'HINDUNILVR', 'ITC', 'SBIN', 'BHARTIARTL', 'KOTAKBANK',
    'LT', 'AXISBANK', 'ASIANPAINT', 'MARUTI', 'BAJFINANCE',
    'TITAN', 'SUNPHARMA', 'ULTRACEMCO', 'NESTLEIND', 'WIPRO'
]

@app.route('/')
def home():
    """Health check endpoint"""
    return jsonify({
        'status': 'online',
        'message': 'NSE Real-Time Data API',
        'version': '1.0.0',
        'endpoints': {
            '/api/stocks': 'Get top stocks data',
            '/api/stock/<symbol>': 'Get specific stock data',
            '/api/indices': 'Get market indices',
            '/api/movers': 'Get top gainers and losers',
            '/api/all': 'Get complete market data'
        }
    })

@app.route('/api/stocks', methods=['GET'])
def get_stocks():
    """Get data for all top stocks"""
    # Check cache
    current_time = time.time()
    if cache['data'] and (current_time - cache['timestamp']) < cache['ttl']:
        logger.info("Returning cached data")
        return jsonify(cache['data']['stocks'])
    
    # Initialize session if needed
    init_nse_session()
    
    stocks_data = []
    for symbol in TOP_STOCKS:
        data = fetch_nse_stock_data(symbol)
        if data:
            stocks_data.append(data)
        time.sleep(0.5)  # Rate limiting
    
    # Update cache
    if not cache['data']:
        cache['data'] = {}
    cache['data']['stocks'] = stocks_data
    cache['timestamp'] = current_time
    
    return jsonify(stocks_data)

@app.route('/api/stock/<symbol>', methods=['GET'])
def get_stock(symbol):
    """Get data for a specific stock"""
    init_nse_session()
    data = fetch_nse_stock_data(symbol.upper())
    
    if data:
        return jsonify(data)
    else:
        return jsonify({'error': 'Failed to fetch stock data'}), 500

@app.route('/api/indices', methods=['GET'])
def get_indices():
    """Get market indices data"""
    # Check cache
    current_time = time.time()
    if cache['data'] and cache['data'].get('indices') and (current_time - cache['timestamp']) < cache['ttl']:
        return jsonify(cache['data']['indices'])
    
    init_nse_session()
    indices = fetch_nse_indices()
    
    # Update cache
    if not cache['data']:
        cache['data'] = {}
    cache['data']['indices'] = indices
    cache['timestamp'] = current_time
    
    return jsonify(indices)

@app.route('/api/movers', methods=['GET'])
def get_movers():
    """Get top gainers and losers"""
    init_nse_session()
    movers = fetch_top_gainers_losers()
    return jsonify(movers)

@app.route('/api/all', methods=['GET'])
def get_all_data():
    """Get complete market data"""
    # Check cache
    current_time = time.time()
    if cache['data'] and (current_time - cache['timestamp']) < cache['ttl']:
        logger.info("Returning complete cached data")
        return jsonify(cache['data'])
    
    init_nse_session()
    
    # Fetch all data
    indices = fetch_nse_indices()
    movers = fetch_top_gainers_losers()
    
    stocks_data = []
    for symbol in TOP_STOCKS[:15]:  # Limit to 15 stocks to reduce load time
        data = fetch_nse_stock_data(symbol)
        if data:
            stocks_data.append(data)
        time.sleep(0.3)
    
    complete_data = {
        'indices': indices,
        'stocks': stocks_data,
        'movers': movers,
        'timestamp': datetime.now().isoformat(),
        'market_status': 'open' if 9 <= datetime.now().hour < 16 else 'closed'
    }
    
    # Update cache
    cache['data'] = complete_data
    cache['timestamp'] = current_time
    
    return jsonify(complete_data)

@app.route('/api/clear-cache', methods=['POST'])
def clear_cache():
    """Clear the cache (admin endpoint)"""
    cache['data'] = None
    cache['timestamp'] = 0
    return jsonify({'message': 'Cache cleared successfully'})

if __name__ == '__main__':
    # Initialize session on startup
    logger.info("Initializing NSE session...")
    init_nse_session()
    logger.info("NSE session initialized")
    
    # Run the server
    app.run(host='0.0.0.0', port=5000, debug=False)

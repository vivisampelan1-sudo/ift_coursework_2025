"""Direct test of yfinance to see if it works."""
import yfinance as yf

print("Testing yfinance directly with AAPL...")
print("="*70)

try:
    stock = yf.Ticker("AAPL")
    info = stock.info
    
    print(f"Company Name: {info.get('longName', 'N/A')}")
    print(f"Current Price: ${info.get('currentPrice', 'N/A')}")
    print(f"Market Cap: ${info.get('marketCap', 'N/A'):,}")
    print(f"P/E Ratio: {info.get('trailingPE', 'N/A')}")
    print(f"P/B Ratio: {info.get('priceToBook', 'N/A')}")
    print(f"EPS: ${info.get('trailingEps', 'N/A')}")
    print(f"Sector: {info.get('sector', 'N/A')}")
    
    print("\n✅ yfinance is working!")
    
except Exception as e:
    print(f"❌ Error: {e}")

print("="*70)

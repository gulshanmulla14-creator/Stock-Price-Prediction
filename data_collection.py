<<<<<<< HEAD
import yfinance as yf

# Download Apple stock data
data = yf.download('AAPL', start='2020-01-01', end='2025-01-01')

# Save data to CSV file
data.to_csv('apple_stock.csv')

=======
import yfinance as yf

# Download Apple stock data
data = yf.download('AAPL', start='2020-01-01', end='2025-01-01')

# Save data to CSV file
data.to_csv('apple_stock.csv')

>>>>>>> b8f160e5449efa8e8041d80c439f442850a9978f
print("✅ Stock data downloaded and saved as apple_stock.csv")
<<<<<<< HEAD
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
import os

# 1. Create models folder if not exists
if not os.path.exists('models'):
    os.makedirs('models')

# 2. Download stock data
data = yf.download('AAPL', start='2015-01-01', end='2025-01-01')
close_prices = data['Close'].values.reshape(-1, 1)

# 3. Scale data
scaler = MinMaxScaler(feature_range=(0,1))
scaled_data = scaler.fit_transform(close_prices)

# Save scaler min and scale for Flask
np.save('models/scaler_min.npy', scaler.min_)
np.save('models/scaler_max.npy', scaler.scale_)

# 4. Prepare training data
X_train = []
y_train = []

for i in range(60, len(scaled_data)):
    X_train.append(scaled_data[i-60:i, 0])
    y_train.append(scaled_data[i, 0])

X_train, y_train = np.array(X_train), np.array(y_train)
X_train = np.reshape(X_train, (X_train.shape[0], X_train.shape[1], 1))

# 5. Build LSTM model
model = Sequential()
model.add(LSTM(units=50, return_sequences=True, input_shape=(X_train.shape[1],1)))
model.add(LSTM(units=50))
model.add(Dense(1))

model.compile(optimizer='adam', loss='mean_squared_error')

# 6. Train model
model.fit(X_train, y_train, epochs=5, batch_size=32)

# 7. Save model
model.save('models/stock_model.h5')
print("✅ Model and scaler saved in 'models/' folder")
=======
import yfinance as yf
import pandas as pd
import numpy as np
from sklearn.preprocessing import MinMaxScaler
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense
import os

# 1. Create models folder if not exists
if not os.path.exists('models'):
    os.makedirs('models')

# 2. Download stock data
data = yf.download('AAPL', start='2015-01-01', end='2025-01-01')
close_prices = data['Close'].values.reshape(-1, 1)

# 3. Scale data
scaler = MinMaxScaler(feature_range=(0,1))
scaled_data = scaler.fit_transform(close_prices)

# Save scaler min and scale for Flask
np.save('models/scaler_min.npy', scaler.min_)
np.save('models/scaler_max.npy', scaler.scale_)

# 4. Prepare training data
X_train = []
y_train = []

for i in range(60, len(scaled_data)):
    X_train.append(scaled_data[i-60:i, 0])
    y_train.append(scaled_data[i, 0])

X_train, y_train = np.array(X_train), np.array(y_train)
X_train = np.reshape(X_train, (X_train.shape[0], X_train.shape[1], 1))

# 5. Build LSTM model
model = Sequential()
model.add(LSTM(units=50, return_sequences=True, input_shape=(X_train.shape[1],1)))
model.add(LSTM(units=50))
model.add(Dense(1))

model.compile(optimizer='adam', loss='mean_squared_error')

# 6. Train model
model.fit(X_train, y_train, epochs=5, batch_size=32)

# 7. Save model
model.save('models/stock_model.h5')
print("✅ Model and scaler saved in 'models/' folder")
>>>>>>> b8f160e5449efa8e8041d80c439f442850a9978f

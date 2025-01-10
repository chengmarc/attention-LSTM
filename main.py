# -*- coding: utf-8 -*-
"""
Created on Wed Jan  8 11:32:34 2025

@author: uzcheng
"""
import os
script_path = os.path.dirname(os.path.realpath(__file__))
os.chdir(script_path)

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import torch
from torch import nn

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print(f"Using device: {device}")


# %%
historic_horizon = 4 * 365  # Use the last 4 years to predict
forecast_horizon = 365  # Predict the next year

from DataPreparation import data

from DataLoader import create_dataloader
dataloader = create_dataloader(data, historic_horizon, forecast_horizon, device, debug=False)

from Seq2SeqLSTM import create_model
model = create_model(data, forecast_horizon, device)


# %%
criterion = nn.MSELoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.0000001)
scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, mode='min', factor=0.8, patience=25)

model.train()
epochs = 1000
for epoch in range(epochs):
    for inputs, targets in dataloader:        
        optimizer.zero_grad()
        
        outputs = model(inputs)
        outputs = outputs.squeeze(-1)        
        targets = targets.squeeze(-1)
        
        loss = criterion(outputs, targets)
        loss.backward()

        # Gradient clipping (optional, for LSTMs)
        #torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)

        optimizer.step()
        
    scheduler.step(loss)
    print(f"Epoch {epoch+1}/{epochs}, Loss: {loss.item():.4f}, LR: {optimizer.param_groups[0]['lr']:.8f}")


# %%
if not os.path.exists('model'):
    os.makedirs('model')

torch.save(model.state_dict(), f'./model/{model.__class__.__name__}-loss-{loss.item():.4f}.pt')
print(f'./model/{model.__class__.__name__}-loss-{loss.item():.4f}.pt Saved.')

model_list = [f'./model/{x}' for x in os.listdir('./model')]
if model_list:
    model_list.sort(key=lambda x: os.path.getmtime(x))
    model.load_state_dict(torch.load(model_list[-1])) #load latest model
    print(f'{model_list[-1]} Loaded.')


# %%
model.eval()
with torch.no_grad():
    predictions = []
    past = torch.tensor(data.iloc[-historic_horizon:, :].values, dtype=torch.float32).unsqueeze(0).to(device)
    pred = model(past)
    predictions.append(pred.cpu().numpy().flatten())  # Flatten the prediction and move to CPU for further processing
    predictions = np.array(predictions).flatten()

# Create DataFrame for predictions
predicted_dates = pd.date_range(start=data.index[-1] + pd.Timedelta(days=1), periods=len(predictions))
predicted_df = pd.DataFrame(predictions, index=predicted_dates, columns=['Predicted PriceUSD'])

# Plot results
plt.figure(figsize=(14, 7))
plt.plot(data.index[-historic_horizon:], data['LogPriceUSD'][-historic_horizon:], label='Log PriceUSD', color='blue')
plt.plot(predicted_df.index, predicted_df['Predicted PriceUSD'], label='Predicted PriceUSD (Next 365 Days)', color='red')
plt.title('Actual vs Predicted PriceUSD for Next 365 Days')
plt.xlabel('Date')
plt.ylabel('PriceUSD')
plt.legend()
plt.show()


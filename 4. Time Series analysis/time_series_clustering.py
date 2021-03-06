#!/usr/bin/env python
# -*- coding: utf-8 -*- 


__author__ = "Theo"



"""--------------------------------------------------------------------
TIME SERIES CLUSTERING
Started on the 2018/03/07

theo.alves.da.costa@gmail.com
https://github.com/theolvs
------------------------------------------------------------------------
"""



# Usual libraries
import os
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import sys
import time
from tqdm import tqdm
import requests
import json

# Plotting libraries
import plotly.graph_objs as go
from plotly.offline import iplot,init_notebook_mode
import cufflinks as cf



#=============================================================================================================================
# ALPHA VANTAGE WRAPPER
#=============================================================================================================================



class AlphaVantage(object):
    """Wrapper for https://www.alphavantage.co/ API
    """
    def __init__(self,api_key):
        self.api_key = api_key
        
    def get(self,ticker):
        data = requests.get("https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={}&apikey={}".format(ticker,self.api_key)).json()
        data = pd.DataFrame(data["Time Series (Daily)"]).astype(float).transpose()
        data.columns = ["open","high","low","close","volume"]
        data.index = pd.to_datetime(data.index)
        return data




#=============================================================================================================================
# COMPANY ONTOLOGIES
#=============================================================================================================================



class Company(object):
    def __init__(self,ticker,alpha = None,data = None):
        self.ticker = ticker

        if data is None:
            self.data = alpha.get(ticker)
        else:
            self.data = data
        
    def __repr__(self):
        return self.ticker


    def get_data(self,variable = "close",normalization = True):
        data = self.data[variable].copy()
        data /= data.max()
        return data


    def get_mono_image(self,variable = "close",window = 7):
        x = self.get_data(variable,normalization = True).as_matrix()
        x = split_array(x,window = window)
        return x


    def show_mono_image(self,variable = "close",window = 7):
        x = self.get_mono_image(variable,window)
        plt.imshow(x)
        plt.title(self.ticker)
        plt.show()

    
    def plot(self,variable = "close"):
        if type(variable) != list: variable = [variable]
        fig = self.data[variable].iplot(world_readable=False,asFigure=True)
        iplot(fig)








def split_array(x,window = 7):
    x = [x[i*window:(i+1)*window] for i in range(int(len(x)/window)+1)]
    x = [y for y in x if len(y) == window]
    x = np.vstack(x)
    return x



#=============================================================================================================================
# COMPANY ONTOLOGIES
#=============================================================================================================================




class Companies(object):
    """Companies wrapper
    """
    def __init__(self,tickers = None,companies = None,json_path = None,alpha = None,max_retries = 5):
        """Initialization
        """
        if companies is not None:
            self.data = companies
        elif tickers is not None:
            self.data,_ = self.get_data(tickers,alpha = alpha,max_retries = max_retries)
        elif json_path is not None:
            self.data = self.load_json_data(json_path)


        self.data = [company for company in self if len(company.data) >= 100]


    #--------------------------------------------------------------------------
    # OPERATORS
            
    def __repr__(self):
        return "{} companies in the dataset".format(len(self))
    
    def __len__(self):
        return len(self.data)
    
    def __iter__(self):
        return iter(self.data)
    
    def __getitem__(self,key):
        if type(key) == int:
            return self.data[key]
        else:
            if type(key) != list : key = [key]
            companies = [company for company in self if company.ticker in key]
            if len(companies) == 1:
                return companies[0]
            else:
                return companies
        
    



    #--------------------------------------------------------------------------
    # IO

    def save_as_json(self,json_path):
        """Save object as json
        """
        data = {}
        for company in self:

            df = company.data.copy()
            df.index = df.index.map(str)
            data[company.ticker] = json.loads(df.to_json())

        with open(json_path, 'w') as file:
            json.dump(data, file,indent = 4,sort_keys = True)


    def load_json_data(self,json_path):
        """Load json data object
        """
        json_data = json.loads(open(json_path,"r").read())
        
        companies = []

        for ticker,data in json_data.items():
            data = pd.DataFrame(data)
            data.index = pd.to_datetime(data.index)

            company = Company(ticker = ticker,data = data)
            companies.append(company)


        return companies





    #--------------------------------------------------------------------------
    # GETTERS


    def get_data(self,tickers,alpha,max_retries = 5):
        """Financial data getter via API
        """
        data = []
        skipped = []
        for ticker in tqdm(tickers,desc = "Acquiring data"):
            try:
                company = Company(ticker,alpha = alpha)
                data.append(company)
            except Exception as e:
                time.sleep(10)
                skipped.append(ticker)

        for i in range(max_retries):
            new_data,skipped = self.get_data(skipped,alpha = alpha,max_retries = 0)
            data.extend(new_data)
            if len(skipped) == 0:
                break

        return data,skipped



    def get_dataframe(self,tickers = None,variable = "close",normalization = True):
        """Create dataframe from companies data
        """
        if tickers is not None:
            companies = self[tickers]
        else:
            companies = self.data       

        data = pd.concat([company.data[[variable]].rename(columns = {variable:company.ticker}) for company in companies],axis = 1)
        
        if normalization:
            data /= data.max(axis = 0)
            
        return data
    


    def build_mono_image_dataset(self):
        """Build mono image dataset
        """
        images = [np.expand_dims(company.get_mono_image(),axis = 0) for company in self]
        images = np.vstack(images)
        return images



    #--------------------------------------------------------------------------
    # VISUALIZATION
    
    def plot(self,tickers = None,variable = "close"):
        """Plot using plotly the set of tickers stock evolution
        """
        data = self.get_dataframe(tickers,variable)
        fig = data.iplot(world_readable=False,asFigure=True)
        iplot(fig)




#=============================================================================================================================
# CNN AUTOENCODER PyTorch
#=============================================================================================================================



import torch
import torchvision
from torch import nn
from torch.autograd import Variable
from torch.utils.data import DataLoader
from torchvision import transforms
from torchvision.utils import save_image



class Autoencoder(nn.Module):
    def __init__(self):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Conv2d(14, 7, 1, stride=1, padding=1),  # b, 16, 10, 10
            nn.ReLU(True),
            nn.MaxPool2d(2, stride=1),  # b, 16, 5, 5
            nn.Conv2d(7, 2, 1, stride=1, padding=1),  # b, 8, 3, 3
            nn.ReLU(True),
            nn.MaxPool2d(2, stride=1)  # b, 8, 2, 2
        )
        self.decoder = nn.Sequential(
            nn.ConvTranspose2d(2, 7, 1, stride=1),  # b, 16, 5, 5
            nn.ReLU(True),
            nn.ConvTranspose2d(7, 14, 1, stride=1, padding=1),  # b, 8, 15, 15
            # nn.ReLU(True),
            # nn.ConvTranspose2d(8, 1, 2, stride=2, padding=1),  # b, 1, 28, 28
            nn.Tanh()
        )

    def forward(self, x):
        if type(x) is type(np.array([])):
            x = Variable(torch.FloatTensor(x))
        x = self.encoder(x)
        x = self.decoder(x)
        return x
    

    def encode(self,x):
        if type(x) is type(np.array([])):
            x = Variable(torch.FloatTensor(x))
        x = self.encoder(x)
        return x
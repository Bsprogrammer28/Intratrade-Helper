# test_india_free.py
from data_india_free import get_intraday_data_india_free

df = get_intraday_data_india_free("RELIANCE", interval="5minute", days=5)
print(df.head())
print(df.tail())
print(df.dtypes)

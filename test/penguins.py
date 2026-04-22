import pandas as pd

penguins = pd.read_csv("./csv/penguins.csv")

# print(penguins.head())
# print(penguins.tail())
# print(penguins.shape)
# print(penguins.info())
print(penguins.describe())

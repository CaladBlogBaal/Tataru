from os import listdir

__cogs__ = ["cogs." + f.replace(".py", "") for f in listdir("cogs") if f != "__pycache__"]

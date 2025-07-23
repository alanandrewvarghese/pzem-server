from fastapi import FastAPI
from power_data import get_power_data

api = FastAPI()

@api.get('/')
def power_data():
    return get_power_data()
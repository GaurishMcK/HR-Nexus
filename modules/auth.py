import random
from modules.database import get_hr_list

def assign_hr_round_robin():
    hr_list = get_hr_list()
    if not hr_list:
        return "Unassigned"
    # In a real app, you'd store the last index in DB. 
    # For now, random acts as a basic load balancer.
    return random.choice(hr_list)
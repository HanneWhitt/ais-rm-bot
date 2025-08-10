from datetime import datetime


# Define your replacements
replacements = {
    '{date}': datetime.now().strftime('%B %d, %Y'),
    
}





def apply_replacements_string(string):



def apply_replacements(data):

    if isinstance(data, str):
        # Base case: if it's a string, apply the string tagging function
        return apply_replacements_string(data)
    elif isinstance(data, dict):
        # Recursively process each value in the dictionary
        return {key: apply_replacements(value, user_dict) for key, value in data.items()}
    elif isinstance(data, list):
        # Recursively process each element in the list
        return [apply_replacements(item, user_dict) for item in data]
    else:
        # For any other data type (int, bool, None, etc.), return as is
        return data





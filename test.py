from urllib.parse import urlparse, parse_qs

# An example string that looks like the one in your output
reference_string = "http://127.0.0.1:5000/Merck%20Veterinary%20Manual%20-%20Canine%20Infectious%20Respiratory%20Disease%20Complex(https://www.merckvetmanual.com/respiratory-system/respiratory-diseases-of-small-animals/canine-infectious-respiratory-disease)"

# Parse the URL
parsed_url = urlparse(reference_string)

# Use parse_qs to extract query parameters if needed
query_params = parse_qs(parsed_url.query)

# Extract the actual URL. In this example, it's wrapped in parentheses
actual_url = reference_string.split('(')[-1].strip(')')

# Now actual_url should contain the correct URL
print(actual_url)

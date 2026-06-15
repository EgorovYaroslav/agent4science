import os
import sys
import requests

# Replace with your FastAPI server URL
API_URL = "https://forecasting.iszf.irk.ru/api/srh/predict"

def predict_image(input_source):
    """
    Sends an image to the FastAPI prediction endpoint.

    Args:
        input_source (str): Either a path to a local image file (.jpg, .png, .fit, .fits)
                            or a URL pointing to a .fit/.fits file

    Returns:
        dict: JSON response from the API
    """
    # Determine if input is a URL or a local file
    if input_source.startswith(("http://", "https://")):
        # print(f"Using remote FITS file from URL: {input_source}")
        params = {"url": input_source}
        files = None
    else:
        if not os.path.isfile(input_source):
            raise FileNotFoundError(f"Image file not found: {input_source}")

        # print(f"Using local file: {input_source}")
        filename = os.path.basename(input_source)
        mime_type = "image/png" if filename.lower().endswith((".png")) else \
                    "image/jpeg" if filename.lower().endswith((".jpg", ".jpeg")) else \
                    "application/fits"
        files = {"file": (filename, open(input_source, "rb"), mime_type)}
        params = None

    # Make request
    response = requests.post(API_URL, files=files, params=params)

    # Handle result
    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Error {response.status_code}: {response.text}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_prediction_request.py <image_path_or_url>")
        sys.exit(1)

    input_source = sys.argv[1]
    try:
        result = predict_image(input_source)
        print(result)
    except Exception as e:
        print("Failed to get prediction:", str(e))
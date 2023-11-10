import gradio as gr
import requests
import inspect
import climateserv.api
from PIL import Image
import os
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt

import os
from dotenv import load_dotenv

load_dotenv(".env")

API_KEY = os.getenv("CHATGPT_API_KEY")


output_file = "out.csv"
output_img = "out.png"

api_endpoint = "https://api.openai.com/v1/completions"
api_key = API_KEY
request_header = {
    "Content-Type": "application/json",
    "Authorization": "Bearer " + api_key
}

datasettype_lookup_table = {
    "centralasiaemodis": "CentralAsia_eMODIS",
    "westafricaemodis": "WestAfrica_eMODIS",
    "eastafricaemodis": "EastAfrica_eMODIS",
    "southafricaemodis": "SouthAfrica_eMODIS",
    "imerg": "IMERG",
    "IMERG": "IMERG",
    "imergearly": "IMERG_early",
    "imerg early": "IMERG_early",
    "chirps": "CHIRPS",
    "rainfall": "CHIRPS",
    "temperature": "TEMPERATURE",
    "precip": "CHIRPS",
    "precipitation": "CHIRPS",
    "smap": "USDA_SMAP",
    "SMAP": "USDA_SMAP",
    "esi": "ESI_4",
    "gefs": "CHIRPS_GEFS_precip_mean",
    "chirps gefs": "CHIRPS_GEFS_precip_mean",
    "CHIRPS GEFS": "CHIRPS_GEFS_precip_mean",
    "chirps_gefs": "CHIRPS_GEFS_precip_mean",
    "chirpsgefs": "CHIRPS_GEFS_precip_mean",
}

reducers_lookup_table = {
    "mean": "Average",
    "average": "Average",
    "max": "Max",
    "maximum": "Max",
    "min": "Min",
    "minimum": "Min",
    "median": "Median",
    "range": "Range",
    "sum": "Sum",
    "total": "Sum",
}

# Format instructions for GPT engine
instructions = f"""I want you to extract five pieces of information from the following prompt.

Extract datasettype, reducertype, startdate, enddate. The startdate and enddate needs to be formatted as MM/DD/YYYY.

I have the lookup table for the datasettype as below
{datasettype_lookup_table}

And the reducertype lookup table looks as below
{reducers_lookup_table}

The fifth value is called bbox which actually is the bounding box represented as an array of five arrays (or list of lists) where each inner array represents comma separated lattitude and longitude in WGS 84 upto 5 decimal places. The five four inner array are the values (latitude and longitude) of the Top-left corner, Top-right corner, Bottom-right corner, Bottom-left corner, and Top-left corner coordinates respectively of the place name from the prompt.

Return these five values separated by commas.

Example prompts:
1. What is the maximum rainfall for Cambodia for first half of 2020? The response should be CHIRPS, Max, 01/01/2020, 06/30/2020, [[102.33909, 14.68949], [107.63234, 14.68949], [107.63234, 9.91276], [102.33909, 9.91276], [102.33909, 14.68949]]
2. What is the average centralasiaemodis value between 2018-01-03 to 2018-03-16 for Kenya? The response should be CentralAsia_eMODIS, Average, 01/03/2018, 03/16/2018, [33.91091, 4.61953], [41.91029, 4.61953], [41.91029, -4.72507], [33.91091, -4.72507], [33.91091, 4.61953]
3. What is the mean smap value for Vietnam for the first quarter of 2019? The response should be USDA_SMAP, Average, 01/01/2019, 03/31/2019, [[102.14146, 23.39179],  [109.46263, 23.39179], [109.46263, 8.410355], [102.14146, 8.410355], [102.14146, 23.39179]]

The prompt is here:
"""

def make_climateserv_request(request_data):
    res = climateserv.api.request_data(
        request_data["dataset_type"],
        request_data["reducer_type"],
        request_data["start_date"],
        request_data["end_date"],
        request_data["bbox"],
        request_data["seasonal_ensemble"],
        request_data["seasonal_variable"],
        output_file
    )
    print(f"res: {res}")
    return res


def make_plot(request_data):
    # Read in the CSV file and ignore the first row
    data = pd.read_csv(output_file, skiprows=[0])

    date_col = data.columns[0]
    val_col = data.columns[1]

    data[date_col] = pd.to_datetime(data[date_col])

    # # Plot the pivoted data as a line chart
    plt.plot(data[date_col], data[val_col])
    plt.xlabel("Date")
    plt.ylabel("Value")
    plt.xticks(rotation=45)
    plt.title(f'Datasettype: {request_data["dataset_type"]}, Reducer: {request_data["reducer_type"]}, Start Date: {request_data["start_date"]},\
              End Date: {request_data["end_date"]}')

    plt.tight_layout()
    plt.savefig(output_img)


def generate_response(user_input):
    print(user_input)
    request_data = {
        "model": "text-davinci-003",
        "prompt": instructions + user_input,
        "max_tokens": 250,
        "temperature": 0.25, # 0.25
    }

    # Send request
    response = requests.post (api_endpoint, headers=request_header, json=request_data)
    # Check for errors
    if response.status_code == 200:
        # Extract response
        print(f"response: {response.json()}")
        parsed = response.json()["choices"][0]["text"]
        # print(f"parsed: {parsed}, type: {type(parsed)}")
        output = inspect.cleandoc(parsed)
        output = output.split(",")
        # return parsed, output
    else:
        print("none found")
        print(response.status_code)
        print(response)
        print ("Request failed with status code: {str(response.status_code)]")

    # Strip white space and make lowercase
    output = [s.strip() for s in output]
    # output = [s.lower() for s in output]

    try:
        dataset_type = datasettype_lookup_table[output[0].strip()]
        reducer_type = reducers_lookup_table[output[1].strip()]
    except KeyError:
        dataset_type = output[0]
        reducer_type = output[1]

    start_date = output[2].strip()
    end_date = output[3].strip()

    try:
        bbox = eval(parsed[parsed.index("["):])
    except:
        bbox = eval(parsed.split("bbox:")[1])   # response[4:]

    # Doesn't run ensemble mode for now
    seasonal_ensemble = False
    seasional_variable = ""

    request_data = {
        "dataset_type": dataset_type,
        "reducer_type": reducer_type,
        "start_date": start_date,
        "end_date": end_date,
        "bbox": bbox if type(bbox) == list else list(bbox),
        "seasonal_ensemble": seasonal_ensemble,
        "seasonal_variable": seasional_variable,
        "llm": True,
    }
    print("request_data")
    print(request_data)

    try:
        os.remove(output_file)
        os.remove(output_img)
    except OSError:
        print("no file to remove")
        pass

    output = make_climateserv_request(request_data)
    # print(f"output: {output}, type: {type(output)}")

    plt.figure().clear()
    plt.close()
    plt.cla()
    plt.clf()
    make_plot(request_data)
    image = Image.open(open(output_img, "rb"))
    return image

# Define the Gradio interface
iface = gr.Interface(
    fn=generate_response,
    inputs=gr.Textbox(label="Enter your CliamteSERV related prompt here...", lines=5),
    outputs=gr.Image(label="Foundational Model response will appear here...", type="pil"),
    # layout="unaligned",
    title="Climate GPT",
    description="Ask me anything! I'm a GPT model specialized in SERVIR's ClimateSERV.",
    examples=[
        ["What is the average centralasiaemodis value between 2018-01-03 to 2018-03-16 for Kenya?"],
        ["What is the maximum rainfall for Cambodia for first half of 2020?"],
        ["What is the mean smap value for Vietnam for the first quarter of 2019?"],
        ["What is the maximum chirps value for Bangladesh for monsoon of 2020?"],
    ],
    # theme="default",
    # theme="huggingface",
    theme = gr.themes.Default(),
    allow_flagging="never",
    css="""
    .input-group {
        background-color: #f9f9f9;
        border: 1px solid #d3d3d3;
        border-radius: 5px;
        padding: 20px;
    }
    .output-group {
        background-color: #f9f9f9;
        border: 1px solid #d3d3d3;
        border-radius: 5px;
        padding: 20px;
    }
    .output {
        font-family: Arial, sans-serif;
        font-size: 1.2em;
        line-height: 1.5em;
        color: #333;
        margin-top: 10px;
    }
    """
)

# Launch the interface
iface.launch()

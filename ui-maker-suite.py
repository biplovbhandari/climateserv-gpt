import gradio as gr
import climateserv.api
from PIL import Image
import os
import pandas as pd
import matplotlib
import google.generativeai as palm
import matplotlib.pyplot as plt

import os
from dotenv import load_dotenv

load_dotenv(".env")
API_KEY = os.getenv("PALM_API_KEY")

output_file = "out.csv"
output_img = "out.png"

palm.configure(api_key=API_KEY)


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
}

# Format instructions for GPT engine
instructions = f"""I want you to extract five pieces of information from the following prompt.
Extract datasettype, reducertype, startdate, enddate. The startdate and enddate are provided as YYYY-MM-DD and they should be formatted as MM/DD/YYYY. \
    The fifth value is called bbox which actually is the bounding box represented as an array of four arrays (or list of lists) where each inner array represents \
        comma separated lattitude and longitude. The four inner array are the value of the Top-left corner, Top-right corner, Bottom-left corner, and Bottom-right corner coordinates of the place name from the prompt. \
        Return these five values separated by commas.
I have the lookup table for the datasettype as below
{datasettype_lookup_table}
And the reducertype lookup table looks as below
{reducers_lookup_table}
The prompt is here \n"""


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
    plt.savefig(output_img, format="png")


def generate_response(user_input):

    request_data = {
      "model": "models/text-bison-001",
      "temperature": 0.1,
      "candidate_count": 1,
      "top_k": 40,
      "top_p": 0.95,
      "max_output_tokens": 1024,
      "stop_sequences": [],
      "safety_settings": [{"category":"HARM_CATEGORY_DEROGATORY","threshold":1},{"category":"HARM_CATEGORY_TOXICITY","threshold":1},{"category":"HARM_CATEGORY_VIOLENCE","threshold":2},{"category":"HARM_CATEGORY_SEXUAL","threshold":2},{"category":"HARM_CATEGORY_MEDICAL","threshold":2},{"category":"HARM_CATEGORY_DANGEROUS","threshold":2}],
    }

    response = palm.generate_text(
      **request_data,
      prompt=instructions + user_input,
    )

    # Check for errors
    # Extract response
    parsed = output = response.to_dict()["candidates"][0]["output"]

    # Split the string at commas
    parts = parsed.split(", ")

    # Separate the list part
    start_index = parsed.find("[")
    end_index = parsed.rfind("]") + 1
    list_part = parsed[start_index: end_index]

    # Get the first parts
    first_parts = parsed[:start_index-1].split(",")

    # Append the list part
    first_parts.append(list_part)

    output = first_parts

    # Strip white space and make lowercase
    output = [s.strip() for s in output]
    print(output)
    print(type(output))

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
    seasonal_ensemble = ""
    seasional_variable = ""

    request_data = {
        "dataset_type": dataset_type,
        "reducer_type": reducer_type,
        "start_date": start_date,
        "end_date": end_date,
        "bbox": bbox,
        "seasonal_ensemble": seasonal_ensemble,
        "seasonal_variable": seasional_variable,
        "llm": True,
    }
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
    outputs=gr.Image(label="Foundational Model response will appear here...", type="pil", show_label=False),
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
    # # theme="huggingface",
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
    .svelte-1mwvhlq {
        display: none;
    }
    """
)

# Launch the interface
iface.launch()

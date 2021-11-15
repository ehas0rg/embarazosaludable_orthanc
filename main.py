#!/usr/bin/python
# -*- coding: UTF-8 -*-

from configparser import ConfigParser
import requests
from requests.auth import HTTPBasicAuth
from datetime import date
import datetime
import time
import logging
import os

# Obtain credentials ###################################################################################################
credentials = {}
parser = ConfigParser()
parser.read("credentials.ini")
params = parser.items("embarazosaludable")  # CHANGE select here your credentials

for param in params:
    credentials[param[0]] = param[1]

DHIS2_SERVER_URL = credentials["dhis2_server"]
DHIS2_SERVER_NAME = credentials["dhis2_server_name"]
DHIS2_USERNAME = credentials["dhis2_user"]
DHIS2_PASSWORD = credentials["dhis2_password"]
DHIS2_PAGESIZE = credentials["dhis2_page_size"]

ORTHANC_SERVER = credentials["orthanc_server"]
ORTHANC_USERNAME = credentials["orthanc_username"]
ORTHANC_PASSWORD = credentials["orthanc_password"]

PROGRAM = "wVXEoaPG9MA"  # Programa Embarazo Saludable
PROGRAM_STAGE = "rnbC8j4Xct0"  # Atención
OU_ROOT = "kOIzn8kS2fR"  # Huehuetenango
DE_ULTRASOUND_DATE = "gvaOAXkGaKW"

DE_TRIMESTRE = "LSy63OWIUJT"

DE_1T = ["QtpIf5fJRwD", "QeSxbCMaAmd"] # CRL, CRL Gemelar
DE_2y3T= ["W8UQrkdmkQN", "Mnfx2QiyhWt", "hCi8La8hX1K", "iqBpedGaObC", "mLDhI8xUyf6", "D2SkGb4y041", "cFWqcDuodl8", "hMluZp0Hyzu","QAJqmb2bRrj", "nxk2xDb9l4D","gCbgrSnE7Hd", "Gm7qJsPq3Lt"]
# DBP, CC, CA, LF, Placenta, Medida Columna Máxima, DBP GEMELAR, CA GEMELAR, CC GEMELAR, LF GEMELAR, PLACENTA GEMELAR, COLUMNA GEMELAR

TEA_CODIGO_CRIBADO = "qNAjhxrtjGp"


# Logging setup ########################################################################################################
today = date.today()
today_str_log = today.strftime("%Y-%m-%d")
check_name = os.path.basename(__file__).replace(".py", "")
DIRECTORY_LOG = "logs"
FILENAME_LOG = DIRECTORY_LOG + "/"+ today_str_log + "-" + DHIS2_SERVER_NAME + "-" + check_name + ".log"

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
# create file handler which logs error messages
fh = logging.FileHandler(FILENAME_LOG, encoding='utf-8')
fh.setLevel(logging.DEBUG)
# create console handler which logs even debug messages
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
# create formatter and add it to the handlers
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
# add the handlers to logger
logger.addHandler(ch)
logger.addHandler(fh)


########################################################################################################################


def get_resources_from_online(parent_resource, fields='*', param_filter=None, parameters=None):
    page = 0
    resources = {parent_resource: []}
    data_to_query = True
    while data_to_query:
        page += 1
        url_resource = DHIS2_SERVER_URL + parent_resource + ".json?fields=" + fields + "&pageSize=" + str(DHIS2_PAGESIZE) + "&format=json&totalPages=true&order=created:ASC&skipMeta=true&page=" + str(page)
        if param_filter:
            url_resource = url_resource + "&" + param_filter
        if parameters:
            url_resource = url_resource + "&" + parameters
        logging.debug(url_resource)
        response = requests.get(url_resource, auth=HTTPBasicAuth(DHIS2_USERNAME, DHIS2_PASSWORD), verify=False)

        if response.ok:
            resources[parent_resource].extend(response.json()[parent_resource])
            if "nextPage" not in response.json()["pager"]:
                data_to_query = False
        else:
            # If response code is not ok (200), print the resulting http error code with description
            response.raise_for_status()

    return resources


def download_image(instance_id):
    logger.info(f"Downloading image from instance {instance_id}")
    path = "images/" + instance_id
    try:
        os.mkdir(path)
    except OSError:
        logger.debug("Creation of the directory %s failed" % path)
    else:
        logger.debug("Successfully created the directory %s " % path)

    url = ORTHANC_SERVER+"/instances/"+instance_id+"/frames/0/preview"

    response = requests.get(url, auth=HTTPBasicAuth(ORTHANC_USERNAME, ORTHANC_PASSWORD), verify=False)
    if response.ok:
        filename = path+"/"+instance_id+".png"
        with open(filename, 'wb') as f:
            f.write(response.content)
            logger.debug(f"Saved {filename}")
        return filename
    else:
        # If response code is not ok (200), print the resulting http error code with description
        response.raise_for_status()


def get_event_uid(event_dict, field, value):
    for event, event_details in event_dict.items():
        for k, v in event_details.items():
            if k == field and v == value:
                return event


def get_image_de_uid(trimestre, de_index):
    if trimestre == "primerTrimestreOpt":
        return DE_1T[de_index]
    elif trimestre in ["segundoTrimestreOpt", "tercerTrimestreOpt"]:
        return DE_2y3T[de_index]
    else:
        return None


def expected_max_number_images(trimestre):
    if trimestre == "primerTrimestreOpt":
        return len(DE_1T)
    elif trimestre in ["segundoTrimestreOpt", "tercerTrimestreOpt"]:
        return len(DE_2y3T)
    else:
        return None # TODO raise error or control the value


# Returns the uid of the fileresource
def post_image_dhis2(filename):
    url_resource = DHIS2_SERVER_URL + "fileResources"
    logging.debug(url_resource)
    files = {'file': open(filename, 'rb')}
    response = requests.post(url_resource, files=files, auth=HTTPBasicAuth(DHIS2_USERNAME, DHIS2_PASSWORD), verify=False)
    logger.debug(response.json())
    if response.ok:
        return response.json()["response"]["fileResource"]["id"]
    else:
        # If response code is not ok (200), print the resulting http error code with description
        response.raise_for_status()


def is_file_storaged(file_resource_uid):
    url_resource = DHIS2_SERVER_URL + "fileResources/" + file_resource_uid
    logging.debug(url_resource)
    response = requests.get(url_resource, auth=HTTPBasicAuth(DHIS2_USERNAME, DHIS2_PASSWORD), verify=False)
    logger.debug(response.json())
    if response.ok:
        if response.json()["storageStatus"] == "STORED":
            return True
        else:
            return False
    else:
        # If response code is not ok (200), print the resulting http error code with description
        response.raise_for_status()


def add_file_to_event(program_uid, event_uid, de_uid, file_resource_uid):
    url_resource = DHIS2_SERVER_URL + "events/"+event_uid+"/"+de_uid
    logging.debug(url_resource)
    data = {"program": program_uid,
            "event": event_uid,
            "dataValues": [{"dataElement": de_uid, "value": file_resource_uid}]
            }
    logging.debug(data)
    response = requests.put(url_resource, json=data, auth=HTTPBasicAuth(DHIS2_USERNAME, DHIS2_PASSWORD), verify=False)
    logger.debug(response.json())
    if response.ok:
        logger.info(f"Updated event {event_uid}. Added DE {de_uid} with file resource {file_resource_uid}")
    else:
        # If response code is not ok (200), print the resulting http error code with description
        response.raise_for_status()


def send_image_to_dhis2(event_uid, image_path, image_de):
    logger.info(f"Event ({event_uid}): Start uploading image to dhis2 '{image_path}' in DE ({image_de})")
    file_resource_uid = post_image_dhis2(image_path)
    logger.info(f"Uploaded file {image_path} to dhis2 and generated a File Resource with uid '{file_resource_uid}'")

    flag_storage_status = False
    while not flag_storage_status:
        logger.info(f"Requesting storage status of dhis2 file resource {file_resource_uid}")
        time.sleep(5)
        flag_storage_status = is_file_storaged(file_resource_uid)
    logger.info(f"File Resource {file_resource_uid} Storage Status already STORAGED")

    # Add FileResource to the event
    add_file_to_event(PROGRAM, event_uid, image_de, file_resource_uid)


########################################################################################################################
########################################################################################################################
########################################################################################################################

# Testing data
# Retrieved for Id Único P0805211cahaPrOr the Series d8527248-83bbb5c5-8a82879a-b0eff1d5-8b12019a
# from the study 33d89009-24a9dc66-7eb18c6b-5e77ebc4-837820bb associated to the event_id DOM98UXXmxV


def main(ultrasound_date):

    ultrasound_date_dhis2 = ultrasound_date.strftime("%Y-%m-%d")

    logger.info("-------------------------------------------")
    logger.info(f"Constants: Program {PROGRAM}.")
    logger.info(f"Starting the process for ultrasound date {ultrasound_date_dhis2}")

    # Get all events without images uploaded
    events_params = "program="+PROGRAM+"&programStage="+PROGRAM_STAGE+"&ou="+OU_ROOT+"&ouMode=DESCENDANTS&paging=false"
    response_events = get_resources_from_online(parent_resource="events", fields="event,trackedEntityInstance,dataValues[*]", param_filter="&filter=" + DE_ULTRASOUND_DATE + ":eq:" + ultrasound_date_dhis2, parameters=events_params)
    logger.info(f"Retrieved {len(response_events['events'])} events for ultrasound date {ultrasound_date_dhis2}")
    events_without_image = {}
    events_with_image = {}  # for debugging
    for event in response_events['events']:
        event_uid = event["event"]
        tei_uid = event["trackedEntityInstance"]
        flag = False

        # get trimestre
        trimestre = None
        for dv in event["dataValues"]:
            if dv["dataElement"] == DE_TRIMESTRE:
                trimestre = dv["value"]
        logging.debug(f"Event={event_uid} Trimestre={trimestre}")

        if not trimestre:
            logger.error(f"Event {event_uid} without trimestre")
            continue # go to the next event

        for dv in event["dataValues"]:
            if dv["dataElement"] == get_image_de_uid(trimestre, de_index=0):  # UID of first image, depending on the semester
                flag = True
        if flag:
            events_with_image[event_uid] = dict()
            events_with_image[event_uid]["tei"] = tei_uid
            events_with_image[event_uid]["trimestre"] = trimestre
        else:
            events_without_image[event_uid] = dict()
            events_without_image[event_uid]["tei"] = tei_uid
            events_without_image[event_uid]["trimestre"] = trimestre

    logger.debug(events_without_image)
    logger.info(f"{len(events_with_image)} events with image: {', '.join(events_with_image)}")
    logger.info(f"{len(events_without_image)} events without image: {', '.join(events_without_image)}")

    teis_without_image = [event["tei"] for event in events_without_image.values()]
    logger.info(f"TEIs without image {teis_without_image}")

    if not events_without_image:
        logger.info(f"There is no events without image. Skip the process.")
        logger.info("-------------------------------------------")
        return None;


    # Revisar que no hay ningun duplicado. Si hay duplicado, eliminar la TEI
    teis_duplicated = {x for x in teis_without_image if teis_without_image.count(x) > 1}

    if teis_duplicated:
        logger.error(f"There are TEIs with more than one event: {teis_duplicated}")
        teis_without_image = set(teis_without_image) - set(teis_duplicated)
        logger.info(f"Removed duplicates: {teis_duplicated}")
        logger.info(f"TEIs without image {teis_without_image}")

    # https://ecopulmonar.dhis2.ehas.org/api/trackedEntityInstances?trackedEntityInstance=gCgxGS7V57A;JaFZxFeJV0d
    teis = ";".join(teis_without_image)
    teis_params = "paging=false&trackedEntityInstance="+teis
    response_teis = get_resources_from_online(parent_resource="trackedEntityInstances", fields="trackedEntityInstance,attributes", parameters=teis_params)
    logger.info(f"Retrieved {len(response_teis['trackedEntityInstances'])} TEIs ({teis})")

    # Check that the amount requested is the same than retrieved
    if len(teis_without_image) != len(response_teis['trackedEntityInstances']):
        logger.error(f"The amount of TEIs requested ({len(teis_without_image)}) is different than the amount of TEIs retrieved ({len(response_teis['trackedEntityInstances'])})")

    # Get TEA 'Código cribado' for each tei in teis_without_image
    id_unicos = set() #id_unico = Código de cribado
    for tei in response_teis['trackedEntityInstances']:
        tei_uid = tei["trackedEntityInstance"]
        for dv in tei["attributes"]:
            if dv["attribute"] == TEA_CODIGO_CRIBADO:  # UID of TEA Código cribado
                id_unico = dv["value"]
                id_unicos.add(id_unico)
                event_uid = get_event_uid(events_without_image, "tei", tei_uid)
                events_without_image[event_uid]["id_unico"] = id_unico
                logger.info(f"Código Cribado '{id_unico}' for TEI '{tei_uid}' from event '{event_uid}'")

    # Check that the amount requested is the same than retrieved
    if len(id_unicos) != len(response_teis['trackedEntityInstances']):
        logger.warning(f"Not all TEIs requested contains a TEA 'Id único')")

    logger.debug(events_without_image)
    logger.info(f"List of Código de Cribado retrieved: {id_unicos}")

    # Retrieve information per patient
    for id_unico in id_unicos:
        study_date = ultrasound_date
        logger.info(f"Requesting {id_unico} in orthanc server for study date {study_date.strftime('%Y%m%d')}")
        url = ORTHANC_SERVER+"/tools/find"
        # data = {
        #     "Level": "Patient",
        #     "Query": {
        #         "PatientID": id_unico
        #     }
        # }
        data = {
            "Level": "Study",
            "Expand": True,
            "Query": {
                "PatientID": id_unico,
                'StudyDate': study_date.strftime("%Y%m%d")
            }
        }
        response_study = requests.post(url, json=data, auth=HTTPBasicAuth(ORTHANC_USERNAME, ORTHANC_PASSWORD), verify=False)
        logger.debug(response_study.json())
        if response_study.ok:
            if not response_study.json():  # Empty response
                logger.info(f"No Study for patient {id_unico} and date {study_date}")
            else:
                patient_id = response_study.json()[0]['ParentPatient']
                study_id = response_study.json()[0]['ID']

                if len(response_study.json()) != 1:  # More than one study in the very same date
                    logger.error(f"Retrieved more than one study for Id Único {id_unico} in {study_date.strftime('%Y%m%d')}'. Result: {response_study.json()} ")
                    continue

                if len(response_study.json()[0]['Series']) != 1:  # More than one series in the same study
                    logger.error(f"Retrieved more than one series in study {study_id} for Id Único {id_unico} in {study_date.strftime('%Y%m%d')}'. Result: {response_study.json()[0]['Series']} ")
                    continue

                series_id = response_study.json()[0]['Series'][0]
                url_series = ORTHANC_SERVER+"/series/"+series_id

                event_uid = get_event_uid(events_without_image, "id_unico", id_unico)
                events_without_image[event_uid]["orthanc_patient"] = patient_id
                events_without_image[event_uid]["orthanc_study"] = study_id
                events_without_image[event_uid]["orthanc_series"] = series_id
                logger.debug(events_without_image)

                logger.info(f"Retrieving instances for Id Único {id_unico} from series {series_id} and study {study_id} associated to event_id {event_uid}")
                response_series_details = requests.get(url_series, auth=HTTPBasicAuth(ORTHANC_USERNAME, ORTHANC_PASSWORD), verify=False)
                logger.debug(response_series_details.json())

                if response_series_details.ok:
                    if response_series_details.json():  # There are instances
                        instances = response_series_details.json()["Instances"]
                        events_without_image[event_uid]["images"] = list()

                        logger.info(f"Retrieved for Id Único {id_unico} and Series {series_id} a total number of {len(instances)} instances.")

                        # Check if it is the number of instances expected
                        if len(instances) > expected_max_number_images(events_without_image[event_uid]["trimestre"]):
                            logger.error(f'Event ({event_uid}). The number of images ({len(instances)}) are different than expected ({expected_max_number_images(events_without_image[event_uid]["trimestre"])})')
                            continue

                        for idx_instances, instance in enumerate(instances):  # Keep the order
                            logger.info(f"Downloading image {idx_instances+1} for instance {instance} and código cribado {id_unico}")
                            image_path = download_image(instance)
                            if image_path:  # image_path could be None if an error occur
                                events_without_image[event_uid]["images"].append(image_path)

                        logger.debug(events_without_image)
                        logger.info(f'{id_unico}: Generated {len(events_without_image[event_uid]["images"])} images for event ({event_uid})')

                        logger.debug(events_without_image[event_uid]["images"])
                        if len(events_without_image[event_uid]["images"]) > expected_max_number_images(events_without_image[event_uid]["trimestre"]):
                            logger.error(f'Event ({event_uid}). The number of images generated ({len(events_without_image[event_uid]["images"])}) are different than expected ({expected_max_number_images(events_without_image[event_uid]["trimestre"])})')
                            continue

                    # Uploading images to dhis2
                    for idx_image, image in enumerate(events_without_image[event_uid]["images"]):
                        logger.info(f"Uploading image {idx_image + 1} for event {event_uid}")
                        image_de = get_image_de_uid(events_without_image[event_uid]["trimestre"], idx_image)
                        send_image_to_dhis2(event_uid, image, image_de)
                    logger.info(f'{id_unico}: Uploaded {len(events_without_image[event_uid]["images"])} images for event ({event_uid})')
                else:
                    # If response code is not ok (200), print the resulting http error code with description
                    response_study.raise_for_status()
        else:
            # If response code is not ok (200), print the resulting http error code with description
            response_study.raise_for_status()
    logger.info(f"Finished the process for ultrasound date {ultrasound_date_dhis2}")
    logger.info("-------------------------------------------")


if __name__ == "__main__":
    start_date = date.today()
    for x in range(1, 7): # TODO change
        ultrasound_date = start_date - datetime.timedelta(days=x)
        main(ultrasound_date)


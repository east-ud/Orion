from whiptail import Whiptail
import logging
import configparser
import os
import utils

log = logging.getLogger(__name__)
log.info("Hello logging!: orion_main is up")

# config
config = configparser.RawConfigParser()
if os.path.isfile('.orion_rc'):
    config.read('.orion_rc')
else:
    utils.create_config()
    config.read('.orion_rc')


## create whiptail for intro menu
def run_menu(conn_obj):

    w = Whiptail(title="ORION V2.0", backtitle="LOAD MENU", auto_exit=True)

    conn_obj.api_name, conn_obj.api_key, conn_obj.secret_key, conn_obj.passphrase = None, 'nothing', 'nothing', 'nothing'

    menu_descriptions = w.menu("Loading menu", [("Start with API connection",
        "Launches full trading (requires passkey)"), ("Start with NO API", "View only"), ("Update settings", "Make changes to configuration file")])[0]

    if menu_descriptions == "Start with API connection":
        # show available encrypted options
        key1 = config['directories']['encoded_key1']
        key2 = config['directories']['encoded_key2']

        key_choice = w.menu(f"Choose API KEYS", [(f"{key1}", ""), (f"{key2}", "")])[0]
        k = w.inputbox("Enter key or blank for no API connection", password=True)[0]
        try:
            keys = utils.readenkjson(key_choice, k)

            conn_obj.api_name = key_choice # used to differentiate betgween different accounts
            log.info(f'reading api key as {key_choice}')
            conn_obj.api_key = keys['g_api_key']  # replace this with your api key
            conn_obj.secret_key = keys['g_secret_key'] # replace this with your api secret
            conn_obj.passphrase = keys['passphrase']

        except Exception as e:
            log.error(e, exc_info=True)
            conn_obj.api_key, conn_obj.secret_key, conn_obj.passphrase = 'nothing', 'nothing', 'nothing'


    elif menu_descriptions == "Update settings":
        menu_settings = w.menu(f"you selected {menu_descriptions}", [("view current settings", ""), ("log directory", "Update location of log files"), ("encrypted api key location", "Update key location"),
            ("email settings", "update email details")])[0]

        if menu_settings == 'view current settings':
            settings = [config.items(section) for section in config.sections()]

            view_box = w.msgbox(f"{settings}")  # type: ignore
            # TODO go back to start menu

        elif menu_settings == "log directory":
            log_directory = str(w.inputbox(f"enter directory location (currently using {config['directories']['logs']})")[0])
            config['directories']['logs'] = log_directory
            log.info(f'updated log directory to {log_directory}')
        elif menu_settings == "encrypted api key location":
            key1_location = str(w.inputbox(f"enter file and location (currently using {config['directories']['encoded_key1']})")[0])
            config['directories']['encoded_key1'] = key1_location
            log.info(f'updated key locaiton to {key1_location}')

        with open('.orion_rc', 'w') as configfile:
            config.write(configfile)
            log.info('saved to config file')



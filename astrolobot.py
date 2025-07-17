import swisseph as swe
from datetime import datetime
import webbrowser
from urllib.parse import quote_plus
from urllib.request import urlretrieve
from threading import Thread
from os import makedirs,path
import http.server
import asyncio
import twitchio
import json

def download_files():
    if not path.exists(script_path()+'swisseph/ephe/'):
        makedirs(script_path()+'swisseph/ephe/')
    #if not path.exists(script_path()+'swisseph/ephe/sefstars.txt'):
    #    print('downloading sefstars.txt')
    #    urlretrieve('https://github.com/aloistr/swisseph/raw/refs/heads/master/ephe/sefstars.txt',script_path()+'swisseph/ephe/sefstars.txt')
    if not path.exists(script_path()+'swisseph/ephe/seas_18.se1'):
        print('downloading seas_18.se1')
        urlretrieve('https://github.com/aloistr/swisseph/raw/refs/heads/master/ephe/seas_18.se1',script_path()+'swisseph/ephe/seas_18.se1')
    #if not path.exists(script_path()+'swisseph/ephe/semo_18.se1'):
    #    print('downloadingh semo_18.se1')
    #    urlretrieve('https://github.com/aloistr/swisseph/raw/refs/heads/master/ephe/semo_18.se1',script_path()+'swisseph/ephe/semo_18.se1')
    #if not path.exists(script_path()+'swisseph/ephe/sepl_18.se1'):
    #    print('downloading sepl_18.se1')
    #    urlretrieve('https://github.com/aloistr/swisseph/raw/refs/heads/master/ephe/sepl_18.se1',script_path()+'swisseph/ephe/sepl_18.se1')
    print('swiss ephemeris files ready')

def get_planet_info():
    # make sure location is set in THIS thread
    swe.set_ephe_path(script_path()+'swisseph/ephe/')
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    # Get current UTC time
    now = datetime.utcnow()
    julian_day = swe.julday(now.year, now.month, now.day)

    # List of planets (Swiss Ephemeris IDs)
    planets = {
        "Sun": swe.SUN,
        "Moon": swe.MOON,
        "Mercury": swe.MERCURY,
        "Venus": swe.VENUS,
        "Mars": swe.MARS,
        "Jupiter": swe.JUPITER,
        "Saturn": swe.SATURN,
        "Uranus": swe.URANUS,
        "Neptune": swe.NEPTUNE,
        "Pluto": swe.PLUTO,
        "Chiron": swe.CHIRON,
        "North Node":swe.TRUE_NODE
    }

    retrograde_info = []
    positions_info = []

    for name, planet_id in planets.items():
        # Get planet position (longitude) and speed
        pos, flags = swe.calc_ut(julian_day, planet_id, swe.FLG_SPEED)

        # Check if retrograde (speed is negative)
        is_retrograde = pos[3] < 0
        if is_retrograde:
            if name=='North Node':
                pass
            else:
                retrograde_info.append(name)

        # Get zodiac sign (0-360° -> Aries to Pisces)
        zodiac_signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
                        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
        sign_num = int(pos[0] // 30)  # 30° per sign
        sign = zodiac_signs[sign_num]
        positions_info.append(f"{name} in {sign}")

        if name=='North Node':
            # rotate sign 180 dagrees
            south_pos=pos[0]+180
            if(south_pos>360):
                south_pos-=360
            # calculate South Node sign
            sign_num = int(south_pos // 30)
            sign = zodiac_signs[sign_num]
            positions_info.append(f"South Node in {sign}")
            
    return retrograde_info, positions_info

async def load_tokens():
    global obs_settings
    obs_tokens=obspython.obs_data_get_obj(obs_settings,'tokens')
    obs_tokens=obspython.obs_data_get_json(obs_tokens)
    obs_tokens=json.loads(obs_tokens)
    for token in obs_tokens.values():
        await client.add_token(token['access'],token['refresh'])

async def save_tokens():
    global obs_settings
    tokens={}
    for user_id in client.tokens:
        token={
            'access':client.tokens[user_id]['token'],
            'refresh':client.tokens[user_id]['refresh'],
        }
        tokens[user_id]=token
    obs_tokens=json.dumps(tokens)
    obs_tokens=obspython.obs_data_create_from_json(obs_tokens)
    obspython.obs_data_set_obj(obs_settings,'tokens',obs_tokens)

async def setup_hook():
    for user_id in client.tokens:
        await client.subscribe_websocket(twitchio.eventsub.ChatMessageSubscription(broadcaster_user_id=user_id,user_id=user_id),token_for=user_id)
        print('connected to channel '+user_id)
    print('astrolobot setup complete')

async def event_message(event):
    if(event.text=='!astrology'):
        retrograde_info, positions_info = get_planet_info()
        await event.broadcaster.send_message(', '.join(retrograde_info)+' in Retrograde',event.broadcaster)
        await event.broadcaster.send_message(', '.join(positions_info[0:2]),event.broadcaster)
        await event.broadcaster.send_message(', '.join(positions_info[2:5]),event.broadcaster)
        await event.broadcaster.send_message(', '.join(positions_info[5:8]),event.broadcaster)
        await event.broadcaster.send_message(', '.join(positions_info[8:11]),event.broadcaster)
        await event.broadcaster.send_message(', '.join(positions_info[11:13]),event.broadcaster)


async def event_oauth_authorized(event):
    await setup_hook()

def main():
    global client, client_id, client_secret, adapter, scopes
    #chdir(script_path())
    scopes = twitchio.Scopes(['user:read:chat','user:write:chat','user:bot','channel:bot'])
    adapter= twitchio.web.AiohttpAdapter(port=8523)
    client = twitchio.Client(client_id=client_id,client_secret=client_secret,scopes=scopes,adapter=adapter)
    client.event_message=event_message
    client.event_oauth_authorized=event_oauth_authorized
    client.setup_hook=setup_hook
    client.save_tokens=save_tokens
    client.load_tokens=load_tokens
    client.run()

twitchio_thread=Thread(target=main,daemon=True)

def get_client_info(*args):
    webbrowser.open('https://dev.twitch.tv/console/apps')

def login(*args):
    global adapter, scopes
    webbrowser.open(adapter.get_authorization_url(scopes=scopes),2,True)

# https://docs.obsproject.com/scripting#script-function-exports

def script_description():
    return 'adds the !astrology command to your twitch channel, providing the current star signs of the planets and whether they are in retrograde'

def script_properties():
    import obspython
    properties=obspython.obs_properties_create()
    obspython.obs_properties_set_flags(properties,obspython.OBS_PROPERTIES_DEFER_UPDATE)
    obspython.obs_properties_add_text(properties,'client_id','Client ID',obspython.OBS_TEXT_PASSWORD)
    obspython.obs_properties_add_text(properties,'client_secret','Client Secret',obspython.OBS_TEXT_PASSWORD)
    obspython.obs_properties_add_button(properties,'client_info','Find Client Info',get_client_info)
    obspython.obs_properties_add_button(properties,'login','Login to Twitch',login)
    return properties

def script_load(settings):
    global obs_settings
    global save

    if not obspython.obs_data_get_bool(settings,'pip_done'):
        import pip,sys
        pip.main(['install','-qqq','pyswisseph','twitchio','twitchio[starlette]','--target',script_path()])
        obspython.obs_data_set_bool(settings,'pip_done',True)
    
    sys.path.append(script_path())
    download_files()

    obs_settings=settings

def script_unload():
    global client
    asyncio.run(client.close())

def script_update(settings):
    global client_id,client_secret
    client_id=obspython.obs_data_get_string(settings,'client_id')
    client_secret=obspython.obs_data_get_string(settings,'client_secret')
    if client_id and client_secret:
        twitchio_thread.start()

if __name__ == '__main__':
    def script_path():
        return path.dirname(__file__)+'/'
    download_files()
    print(get_planet_info())
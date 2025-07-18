from datetime import datetime,timezone
import webbrowser
from urllib.parse import quote_plus
from urllib.request import urlretrieve
from threading import Thread
from os import makedirs,path
import http.server
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


zodiac_signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

def get_planet_info(date):
    import swisseph as swe
    # make sure location is set in THIS thread
    swe.set_ephe_path(script_path()+'swisseph/ephe/')
    swe.set_sid_mode(swe.SIDM_LAHIRI)
    # Get current UTC time
    julian_day = swe.julday(date.year, date.month, date.day)

    # List of planets (Swiss Ephemeris IDs)
    planets = {
        "The Sun": swe.SUN,
        "The Moon": swe.MOON,
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
    positions_info = {}

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
        sign_num = int(pos[0] // 30)  # 30° per sign
        positions_info[name]=sign_num

        if name=='North Node':
            # rotate sign 180 dagrees
            south_pos=pos[0]+180
            if(south_pos>360):
                south_pos-=360
            # calculate South Node sign
            sign_num = int(south_pos // 30)
            positions_info['South Node']=sign_num

    return {
        'positions': positions_info,
        'retrograde': retrograde_info,
    }

def get_planet_info_formatted(date=datetime.utcnow()):
    planets=get_planet_info(date)
            
    match len(planets['retrograde']):
            case 0:
                info=''
            case 1:
                info=planets['retrograde'][0]+' is in Retrograde'
            case 2:
                info=' and '.join(planets['retrograde'])+' are in Retrograde'
            case _:
                info=', '.join(planets['retrograde'][0:-1])+', and '+planets['retrograde'][-1]+' are in Retrograde'

    positions_info=[]
    for planet,position in planets['positions'].items():
        positions_info.append(planet+' is in '+zodiac_signs[position])

    info+='\n'+', '.join(positions_info[0:2])
    info+='\n'+', '.join(positions_info[2:5])
    info+='\n'+', '.join(positions_info[5:8])
    info+='\n'+', '.join(positions_info[8:11])
    info+='\n'+', '.join(positions_info[11:13])
    return info

def get_transits():
    seconds_in_1_day=86400
    now=datetime.utcnow()
    positions_today=get_planet_info(now)
    position_updates={}
    days=1
    date_format='%b %-d'
    while len(position_updates)<12 and days<29:
        future_timestamp=now.timestamp()+(days*seconds_in_1_day)
        future_date=datetime.fromtimestamp(future_timestamp,timezone.utc)
        positions_future=get_planet_info(future_date)
        for planet in positions_future['retrograde']:
            if planet not in positions_today['retrograde'] and planet not in position_updates.keys():
                position_updates[planet]='entering Retrograde on '+future_date.strftime(date_format)
        for planet in positions_today['retrograde']:
            if planet not in positions_future['retrograde'] and planet not in position_updates.keys():
                position_updates[planet]='exiting Retrograde on '+future_date.strftime(date_format)
        for planet in positions_future['positions']:
            if positions_today['positions'][planet]!=positions_future['positions'][planet] and planet not in position_updates.keys():
                position_updates[planet]='entering '+zodiac_signs[positions_future['positions'][planet]]+' on '+future_date.strftime(date_format)
        days+=1
    return position_updates        

def get_transits_formatted():
    transits=get_transits()
    info=''
    for planet,transit in transits.items():
        info+='\n'+planet+' is '+transit
    return info

async def load_tokens():
    global obs_settings
    obs_tokens=obspython.obs_data_get_obj(obs_settings,'tokens')
    obs_tokens=obspython.obs_data_get_json(obs_tokens)
    if not obs_tokens:
        return
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
    import twitchio
    for user_id in client.tokens:
        await client.subscribe_websocket(twitchio.eventsub.ChatMessageSubscription(broadcaster_user_id=user_id,user_id=user_id),token_for=user_id)
        print('connected to channel '+user_id)
    print('astrolobot setup complete')

async def event_message(event):
    if(event.text=='!astrology'):
        info = get_planet_info_formatted()
        for line in info.splitlines(False):
            if line:
                await event.broadcaster.send_message(line,event.broadcaster)
    if(event.text=='!transits'):
        info = get_transits_formatted()
        for line in info.splitlines(False):
            if line:
                await event.broadcaster.send_message(line,event.broadcaster)

async def event_oauth_authorized(event):
    await setup_hook()

def main():
    import twitchio
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
    import sys
    global obs_settings
    global save

    if not obspython.obs_data_get_bool(settings,'pip_done'):
        import pip
        pip.main(['install','-qqq','pyswisseph','twitchio','twitchio[starlette]','--target',script_path()])
        obspython.obs_data_set_bool(settings,'pip_done',True)
    
    sys.path.append(script_path())
    download_files()

    obs_settings=settings

def script_unload():
    global client
    import asyncio
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
    print(get_planet_info_formatted())
    print(get_transits_formatted())
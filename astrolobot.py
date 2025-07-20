#!/usr/bin/env python3.11

from datetime import datetime,timezone
from urllib.parse import quote_plus
from urllib.request import urlretrieve, urlopen, Request, HTTPError
from threading import Thread
from os import makedirs,path
import json,sys,webbrowser,importlib

def dependency_setup():
    print('checking dependencies')
    from pip._internal.cli.main import main as pip
    pip(['install','-qq','pyswisseph','twitch.py','--target',script_path()+'pip'])
    sys.path.append(script_path()+'pip')

    if not path.exists(script_path()+'ephe/seas_18.se1'):
        print('downloading database')
        makedirs(script_path()+'ephe')
        urlretrieve('https://github.com/aloistr/swisseph/raw/refs/heads/master/ephe/seas_18.se1',script_path()+'ephe/seas_18.se1')

    print('dependencies ready')

# Astrology functions

zodiac_signs = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]

def get_planet_info(date):
    import swisseph as swe
    # make sure location is set in THIS thread
    swe.set_ephe_path(script_path()+'ephe/')
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
                info=planets['retrograde'][0]+' is in Retrograde\n'
            case 2:
                info=' and '.join(planets['retrograde'])+' are in Retrograde\n'
            case _:
                info=', '.join(planets['retrograde'][0:-1])+', and '+planets['retrograde'][-1]+' are in Retrograde\n'

    positions_info=[]
    for planet,position in planets['positions'].items():
        positions_info.append(planet+' is in '+zodiac_signs[position])

    info+=', '.join(positions_info[0:2])+'\n'
    info+=', '.join(positions_info[2:5])+'\n'
    info+=', '.join(positions_info[5:8])+'\n'
    info+=', '.join(positions_info[8:11])+'\n'
    info+=', '.join(positions_info[11:13])+'\n'
    return info

def get_transits():
    seconds_in_1_day=86400
    now=datetime.utcnow()
    positions_today=get_planet_info(now)
    position_updates={}
    days=1
    date_format='%b %d'
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
        info+=planet+' is '+transit+'\n'
    return info

# Twitch functions

device_code=None

def login(*args):
    global device_code
    if device_code==None:
        print('astrolobot is still starting, please wait',sys.stderr)
    webbrowser.open('https://www.twitch.tv/activate?public=true&device-code='+device_code)

def save_tokens(access_token,refresh_token):
    with open(script_path()+'tokens.json','w') as file:
        json.dump(
            {
                'access_token':access_token,
                'refresh_token':refresh_token,
            },
            file
        )
    print('login tokens saved to '+script_path()+'tokens.json')

def load_tokens():
    try:
        with open(script_path()+'tokens.json','r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def refresh_tokens(refresh_token):
    print('refreshing login tokens')
    global client
    refresh_request=Request(
        'https://id.twitch.tv/oauth2/token',
        (
            'client_id='+client.client_id
            +'&grant_type=refresh_token'
            +'&refresh_token='+refresh_token
        ).encode(),
        {'Content-Type':'application/x-www-form-urlencoded'}
    )
    try:
        refresh_response=urlopen(refresh_request)
        refresh_response=json.loads(refresh_response.read())
        save_tokens(refresh_response['access_token'],refresh_response['refresh_token'])
        return{
            'access_token':refresh_response['access_token'],
            'refresh_token':refresh_response['refresh_token'],
        }
    except HTTPError:
        print('refreshing tokens failed')
        return {}

def main():
    from twitch import Client
    from twitch.types import eventsub
    from twitch.ext.oauth import DeviceAuthFlow, Scopes
    import asyncio
    global client
    client = Client(client_id='h08yimv2stqxci85tpfh5k7t16an2u')
    tokens=load_tokens()
    if len(tokens)!=0:
        tokens=refresh_tokens(tokens['refresh_token'])
    DeviceAuthFlow(
        client=client,
        scopes=[
            Scopes.CHANNEL_BOT,
            Scopes.USER_BOT,
            Scopes.USER_READ_CHAT,
            Scopes.USER_WRITE_CHAT,
        ],
        wrap_run=len(tokens)==0
    )

    @client.event
    async def on_code(code: str):
        global device_code, obs_settings
        device_code=code
        if obs_settings == None:
            login()

    @client.event
    async def on_auth(access_token: str, refresh_token: str):
        save_tokens(access_token,refresh_token)

    @client.event
    async def on_ready() -> None:
        print('astrolobot ready')
        while True:
            tokens=client.http.get_token(client.user.id)
            await asyncio.sleep(tokens['expire_in']*0.9)
            tokens=refresh_tokens(tokens['refresh_token'])
            await client.authorize(tokens['access_token'],tokens['refresh_token'])

    @client.event
    async def on_chat_message(data: eventsub.chat.MessageEvent):
        if data['message']['text']=='!astrology':
            for line in get_planet_info_formatted().splitlines(False):
                await client.channel.chat.send_message(line,data['message_id'])
            return
        if data['message']['text']=='!transits':
            for line in get_transits_formatted().splitlines(False):
                await client.channel.chat.send_message(line,data['message_id'])

    client.run(*tokens.values())

# OBS functions

obs_settings=None

def script_main():
    dependency_setup()
    main()
    
def obs_load_tokens():
    import obspython
    access_token=obspython.obs_data_get_string(obs_settings,'access_token')
    refresh_token=obspython.obs_data_get_string(obs_settings,'refresh_token')
    if not (access_token or refresh_token):
        print('astrolobot: login required',file=sys.stderr)
        return {}
    else:
        return {
            'access_token':access_token,
            'refresh_token':refresh_token,
        }

def obs_save_tokens(access_token,refresh_token):
    import obspython
    obspython.obs_data_set_string(obs_settings,'access_token',access_token)
    obspython.obs_data_set_string(obs_settings,'refresh_token',refresh_token)
    print('login tokens saved to OBS')

# https://docs.obsproject.com/scripting#script-function-exports

def script_description():
    return 'adds the !astrology and !transits commands to your twitch channel, providing the current and upcoming star signs and retrograde status of the planets'

def script_properties():
    import obspython
    properties=obspython.obs_properties_create()
    obspython.obs_properties_add_button(properties,'login','Login to Twitch',login)
    return properties

def script_load(settings):
    global obs_settings, save_tokens, load_tokens
    obs_settings=settings
    save_tokens=obs_save_tokens
    load_tokens=obs_load_tokens
    def isatty():
        return False
    sys.stdout.isatty=isatty
    Thread(target=script_main,daemon=True).start()

def script_unload():
    try:
        import asyncio
        global client
        asyncio.run(client.close())
    except NameError or ImportError:
        pass

# test functions

if __name__ == '__main__':
    def script_path():
        return path.dirname(__file__)+'/'
    dependency_setup()
    print(get_planet_info_formatted())
    print(get_transits_formatted())
    main()
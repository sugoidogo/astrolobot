#!/usr/bin/env python3.11

from datetime import datetime,timezone
from urllib.parse import quote_plus
from urllib.request import urlretrieve, urlopen, Request, HTTPError
from threading import Thread
from os import makedirs,path
from functools import cache
import json,sys,webbrowser,importlib,tomllib

def update():
    print('checking for updates...')
    with open(script_path()+'astrolobot.py','r') as file:
        current_script=file.read()
    urlretrieve(
        'https://github.com/sugoidogo/astrolobot/releases/latest/download/astrolobot.py',
        script_path()+'astrolobot.py'
    )
    with open(script_path()+'astrolobot.py','r') as file:
        updated_script=file.read()
    if current_script==updated_script:
        print('up to date')
    else:
        print('update downloaded, restart script to apply')

def dependency_setup():
    if not path.exists(script_path()+'pip'):
        print('installing dependencies')
        from pip._internal.cli.main import main as pip
        pip(['install','-qq','pyswisseph','twitch.py','--target',script_path()+'pip'])
       
    sys.path.append(script_path()+'pip')

    if not path.exists(script_path()+'ephe/seas_18.se1'):
        print('downloading database')
        makedirs(script_path()+'ephe')
        urlretrieve('https://github.com/aloistr/swisseph/raw/refs/heads/master/ephe/seas_18.se1',script_path()+'ephe/seas_18.se1')
    
    import swisseph as swe
    swe.set_ephe_path(script_path()+'ephe/')
    swe.set_sid_mode(swe.SIDM_LAHIRI)

    print('dependencies ready')

def today():
    now=datetime.utcnow()
    return datetime(now.year,now.month,now.day)

# Astrology functions

def load_settings():
    try:
        with open(script_path()+'config.toml','r') as file:
            return tomllib.loads(file.read())
    except FileNotFoundError:
        return {
            'positions':'!positions',
            'transits':'!transits',
            'major_aspects':'!aspects major',
            'minor_aspects':'!aspects minor',
            'major_aspect_transits':'!aspects major transits',
            'minor_aspect_transits':'!aspects minor transits',
        }

def get_zodiac(angle):
    zodiac = ["Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo", 
        "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces"]
    return zodiac[int(angle//30)]

def is_retrograde(speed):
    return speed<0

@cache
def get_positions_raw(date=today()):
    import swisseph as swe
    julian_day = swe.julday(date.year, date.month, date.day)
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
    positions={}

    for planet_name, planet_id in planets.items():
        position, _ = swe.calc_ut(julian_day, planet_id, swe.FLG_SPEED)
        positions[planet_name]={
            'angle':position[0],
            'speed':position[3],
        }
        if planet_name=='North Node':
            positions['South Node']={
                'angle':(position[0]+180)%360,
                'speed':position[3],
            }

    return positions

@cache
def get_positions(date=today()):
    positions={}

    for name, position_raw in get_positions_raw(date).items():
        positions[name]={
            'zodiac':get_zodiac(position_raw['angle']),
            'retrograde':is_retrograde(position_raw['speed']),
        }

    return positions

def get_list_formatted(in_list,isare=False):
    match len(in_list):
        case 0:
            output='Nothing'
            if isare:
                output+=' is '
        case 1:
            output=in_list[0]
            if isare:
                output+=' is '
        case 2:
            output=' and '.join(in_list)
            if isare:
                output+=' are '
        case _:
            output=', '.join(in_list[0:-1])+', and '+in_list[-1]
            if isare:
                output+=' are '
    return output

@cache
def get_positions_formatted(date=today()):
    retrograde_planets=[]
    position_strings=[]

    for name, position in get_positions(date).items():
        if(position['retrograde']):
            retrograde_planets.append(name)
        position_strings.append(name+' is in '+position['zodiac'])
    
    positions_formatted=get_list_formatted(retrograde_planets,True)+'in Retrograde\n'

    positions_formatted+=', '.join(position_strings[0:2])+'\n'
    positions_formatted+=', '.join(position_strings[2:5])+'\n'
    positions_formatted+=', '.join(position_strings[5:8])+'\n'
    positions_formatted+=', '.join(position_strings[8:11])+'\n'
    positions_formatted+=', '.join(position_strings[11:13])+'\n'
    
    return positions_formatted

seconds_in_1_day=86400

@cache
def get_transits(date=today(), maxdays=28):
    positions_now=get_positions(date)
    transits={}
    days=1

    while len(transits)<12 and days<=maxdays:
        future_timestamp=date.timestamp()+(days*seconds_in_1_day)
        future_date=datetime.fromtimestamp(future_timestamp,timezone.utc)
        positions_future=get_positions(future_date)
        for name, position_future in positions_future.items():
            position_now=positions_now[name]
            if name not in transits and position_now!=position_future:
                position_future['date']=future_date
                if position_now['zodiac']==position_future['zodiac']:
                    position_future['zodiac']=None
                if position_now['retrograde']==position_future['retrograde']:
                    position_future['retrograde']=None
                transits[name]=position_future
        days+=1
    
    return transits

date_format='%b %d'

@cache
def get_transits_formatted(date=today(), maxdays=28):
    transits_formatted=''

    for name,transit in get_transits(date, maxdays).items():
        if transit['zodiac']!=None:
            transits_formatted+=name+' is entering '+transit['zodiac']+' on '+transit['date'].strftime(date_format)+'\n'
        if transit['retrograde']==True:
            transits_formatted+=name+' is entering Retrograde on '+transit['date'].strftime(date_format)+'\n'
        if transit['retrograde']==False:
            transits_formatted+=name+' is exiting Retrograde on '+transit['date'].strftime(date_format)+'\n'
        
    return transits_formatted

@cache
def get_aspects(date=today(), minor=False):
    positions=get_positions_raw(date).copy()
    major_aspects={
        'conjuction':{'angle':0,'orb':10.0},
        'oposition':{'angle':180,'orb':10.0},
        'trine':{'angle':120,'orb':10.0},
        'square':{'angle':90,'orb':10.0},
        'sextile':{'angle':60,'orb':5.0},
    }
    minor_aspects={
        'semi-sextile':{'angle':30,'orb':1.5},
        'inconjunct':{'angle':150,'orb':3},
        'semi-square':{'angle':45,'orb':3},
        'trioctile':{'angle':135,'orb':3},
        'quintile':{'angle':72,'orb':1},
        'biquintile':{'angle':144,'orb':1},
    }
    aspects={}
    if minor:
        selected_aspects=minor_aspects
    else:
        selected_aspects=major_aspects

    for aname, aposition in positions.copy().items():
        del positions[aname]
        if aname.endswith('Node'):
            continue
        planet_aspects={}
        for bname, bposition in positions.items():
            angle_diff=abs(aposition['angle']-bposition['angle'])
            for aspect_name,aspect in selected_aspects.items():
                aspect_max=(aspect['angle']+aspect['orb'])%360
                aspect_min=(aspect['angle']-aspect['orb'])%360
                if aspect_min<angle_diff<aspect_max:
                    try:
                        planet_aspects[aspect_name].append(bname)
                    except KeyError:
                        planet_aspects[aspect_name]=[bname]
        if len(planet_aspects)!=0:
            aspects[aname]=planet_aspects

    return aspects

@cache
def get_aspects_formatted(date=today(),minor=False):
    aspects_formatted=''

    for planet,aspects in get_aspects(date,minor).items():
        aspects_formatted+=planet+' is in '
        aspects_list=[]
        for aspect_name,aspect_planets in aspects.items():
            aspects_list.append(aspect_name+' with '+get_list_formatted(aspect_planets))
        aspects_formatted+=get_list_formatted(aspects_list)+'\n'

    return aspects_formatted

@cache
def get_aspect_transits(date=today(),minor=False,maxdays=28):
    date_now=today()
    timestamp_now=date_now.timestamp()
    aspects_now=get_aspects(date_now,minor)
    pre_transits={}
    days=0

    def aspects_contains(aspects,planet_a,aspect=None,planet_b=None):
        if planet_a not in aspects:
            return False
        elif aspect and aspect not in aspects[planet_a]:
            return False
        elif aspect and planet_b and planet_b not in aspects[planet_a][aspect]:
            return False
        return True

    def ensure_pre_path(planet_a,aspect=None):
        if planet_a not in pre_transits:
            pre_transits[planet_a]={}
        if aspect and aspect not in pre_transits[planet_a]:
            pre_transits[planet_a][aspect]={}

    def pre_planet_b(planet_a,aspect,planet_b,date_future,direction):
        ensure_pre_path(planet_a,aspect)
        pre_transits[planet_a][aspect][planet_b]={
            'date':date_future,
            'direction':direction
        }

    def pre_aspect(planet_a,aspect,planets,date_future,direction):
        ensure_pre_path(planet_a)
        pre_transits[planet_a][aspect]={}
        for planet_b in planets:
            pre_planet_b(planet_a,aspect,planet_b,date_future,direction)

    def pre_planet_a(planet_a,aspects,date_future,direction):
        pre_transits[planet_a]={}
        for aspect,planets in aspects.items():
            pre_aspect(planet_a,aspect,planets,date_future,direction)

    while days<maxdays:
        days+=1
        timestamp_future=timestamp_now+(seconds_in_1_day*days)
        date_future=datetime.fromtimestamp(timestamp_future,timezone.utc)
        aspects_future=get_aspects(date_future)
        for planet_a,aspects in aspects_now.items():
            try:
                pre_transits[planet_a]
            except KeyError:
                if not aspects_contains(aspects_future,planet_a):
                    pre_planet_a(planet_a,aspects,date_future,'exiting')
                    continue
            for aspect, planets in aspects.items():
                try:
                    pre_transits[planet_a][aspect]
                except KeyError:
                    if not aspects_contains(aspects_future,planet_a,aspect):
                        pre_aspect(planet_a,aspect,planets,date_future,'exiting')
                        continue
                    for planet_b in planets:
                        try:
                            pre_transits[planet_a][aspect][planet_b]
                        except KeyError:
                            if not aspects_contains(aspects_future,planet_a,aspect,planet_b):
                                pre_planet_b(planet_a,aspect,planet_b,date_future,'exiting')
    
    days=0
    while days<maxdays:
        days+=1
        timestamp_future=timestamp_now+(seconds_in_1_day*days)
        date_future=datetime.fromtimestamp(timestamp_future,timezone.utc)
        aspects_future=get_aspects(date_future)
        for planet_a,aspects in aspects_future.items():
            try:
                pre_transits[planet_a]
            except KeyError:
                if not aspects_contains(aspects_now,planet_a):
                    pre_planet_a(planet_a,aspects,date_future,'entering')
                    continue
            for aspect, planets in aspects.items():
                try:
                    pre_transits[planet_a][aspect]
                except KeyError:
                    if not aspects_contains(aspects_now,planet_a,aspect):
                        pre_aspect(planet_a,aspect,planets,date_future,'entering')
                        continue
                    for planet_b in planets:
                        try:
                            pre_transits[planet_a][aspect][planet_b]
                        except KeyError:
                            if not aspects_contains(aspects_now,planet_a,aspect,planet_b):
                                pre_planet_b(planet_a,aspect,planet_b,date_future,'entering')

    post_transits={}

    for planet_a,aspects in pre_transits.items():
        post_transits[planet_a]={}
        for aspect,planets in aspects.items():
            for planet_b,transit in planets.items():
                direction=transit['direction']
                date=transit['date']
                if direction not in post_transits[planet_a]:
                    post_transits[planet_a][direction]={}
                if date not in post_transits[planet_a][direction]:
                    post_transits[planet_a][direction][date]={}
                if aspect not in post_transits[planet_a][direction][date]:
                    post_transits[planet_a][direction][date][aspect]=[]
                post_transits[planet_a][direction][date][aspect].append(planet_b)

    return post_transits

@cache
def get_aspect_transits_formatted(date=today(),minor=False,maxdays=28):
    aspect_transits=get_aspect_transits(date,minor,maxdays)
    aspect_transits_formatted=''

    for planet_a,directions in aspect_transits.items():
        aspect_transits_formatted+=planet_a+' is '
        direction_list=[]
        for direction,dates in directions.items():
            date_list=[]
            for date,aspects in dates.items():
                aspect_list=[]
                for aspect,planets in aspects.items():
                    aspect_list.append(aspect+' with '+get_list_formatted(planets))
                date_list.append(get_list_formatted(aspect_list)+' on '+date.strftime(date_format))
            direction_list.append(direction+' '+get_list_formatted(date_list))
        aspect_transits_formatted+=get_list_formatted(direction_list)+'\n'
    
    return aspect_transits_formatted

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
        config=load_settings()
        if data['message']['text']==config['positions']:
            for line in get_positions_formatted().splitlines(False):
                await client.channel.chat.send_message(line,data['message_id'])
            return
        if data['message']['text']==config['transits']:
            for line in get_transits_formatted().splitlines(False):
                await client.channel.chat.send_message(line,data['message_id'])
            return
        if data['message']['text']==config['major_aspects']:
            for line in get_aspects_formatted().splitlines(False):
                await client.channel.chat.send_message(line,data['message_id'])
            return
        if data['message']['text']==config['minor_aspects']:
            for line in get_aspects_formatted(minor=True).splitlines(False):
                await client.channel.chat.send_message(line,data['message_id'])
            return
        if data['message']['text']==config['major_aspect_transits']:
            for line in get_aspect_transits_formatted().splitlines(False):
                await client.channel.chat.send_message(line,data['message_id'])
            return
        if data['message']['text']==config['minor_aspect_transits']:
            for line in get_aspect_transits_formatted(minor=True).splitlines(False):
                await client.channel.chat.send_message(line,data['message_id'])
            return

    client.run(*tokens.values())

# OBS functions

obs_settings=None

def script_main():
    dependency_setup()
    main()

def obs_update(*args):
    Thread(target=update,daemon=True).start()

def obs_load_settings():
    import obspython
    global obs_settings
    settings=json.loads(obspython.obs_data_get_json_with_defaults(obs_settings))
    return settings
    
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
    return 'adds astrology commands to your twitch channel, providing the current and upcoming star signs and retrograde status of the planets'

def script_properties():
    import obspython
    properties=obspython.obs_properties_create()
    obspython.obs_properties_add_button(properties,'login','Login to Twitch',login)
    obspython.obs_properties_add_button(properties,'update','Check for Updates',obs_update)
    obspython.obs_properties_add_text(properties,'commands','commands',obspython.OBS_TEXT_INFO)
    obspython.obs_properties_add_text(properties,'positions','positions',obspython.OBS_TEXT_DEFAULT)
    obspython.obs_properties_add_text(properties,'transits','transits',obspython.OBS_TEXT_DEFAULT)
    obspython.obs_properties_add_text(properties,'major_aspects','major aspects',obspython.OBS_TEXT_DEFAULT)
    obspython.obs_properties_add_text(properties,'minor_aspects','minor aspects',obspython.OBS_TEXT_DEFAULT)
    obspython.obs_properties_add_text(properties,'major_aspect_transits','major aspect transits',obspython.OBS_TEXT_DEFAULT)
    obspython.obs_properties_add_text(properties,'minor_aspect_transits','minor aspect transits',obspython.OBS_TEXT_DEFAULT)
    return properties

def script_defaults(settings):
    import obspython
    obspython.obs_data_set_default_string(settings,'commands','you can change the commands below, they save automatically')
    obspython.obs_data_set_default_string(settings,'positions','!positions')
    obspython.obs_data_set_default_string(settings,'transits','!transits')
    obspython.obs_data_set_default_string(settings,'major_aspects','!aspects major')
    obspython.obs_data_set_default_string(settings,'minor_aspects','!aspects minor')
    obspython.obs_data_set_default_string(settings,'major_aspect_transits','!aspects major transits')
    obspython.obs_data_set_default_string(settings,'minor_aspect_transits','!aspects minor transits')

def script_load(settings):
    global obs_settings, save_tokens, load_tokens, load_settings
    obs_settings=settings
    save_tokens=obs_save_tokens
    load_tokens=obs_load_tokens
    load_settings=obs_load_settings
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

def script_update(settings):
    global obs_settings
    obs_settings=settings

# test functions

if __name__ == '__main__':
    def script_path():
        return path.dirname(__file__)+'/'
    dependency_setup()
    print(get_positions_formatted())
    print(get_transits_formatted())
    print(get_aspects_formatted())
    print(get_aspects_formatted(minor=True))
    print(get_aspect_transits_formatted())
    print(get_aspect_transits_formatted(minor=True))
    main()
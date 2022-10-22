from cProfile import Profile
from contextvars import Token
from http import client
from pydoc import describe
import discord, json, requests, os, httpx, base64, time, subprocess
from discord.ext.commands import Bot
from discord.ext import commands, tasks
from colorama import Fore, init
from functools import wraps 
from discord import bot
import datetime
import time


from asyncio.proactor_events import _ProactorBasePipeTransport


def getchecksum():
	path = os.path.basename(__file__)
	if not os.path.exists(path):
		path = path[:-2] + "exe"
	md5_hash = hashlib.md5()
	a_file = open(path,"rb")
	content = a_file.read()
	md5_hash.update(content)
	digest = md5_hash.hexdigest()
	return digest
                                                


def silence_event_loop_closed(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)
        except RuntimeError as e:
            if str(e) != 'Event loop is closed':
                raise
    return wrapper

_ProactorBasePipeTransport.__del__ = silence_event_loop_closed(_ProactorBasePipeTransport.__del__)

bot = discord.Bot(intents=discord.Intents.all())
settings = json.load(open("settings.json", encoding="utf-8"))

if not os.path.isfile("used.json"):
    used = {}
    json.dump(used, open("used.json", "w", encoding="utf-8"), indent=4)

used = json.load(open("used.json"))

def isAdmin(ctx):
    return str(ctx.author.id) in settings["botAdminId"]


def makeUsed(token: str):
    data = json.load(open('used.json', 'r'))
    with open('used.json', "w") as f:
        if data.get(token): return
        data[token] = {
            "boostedAt": str(time.time()),
            "boostFinishAt": str(time.time() + 30 * 86400)
        }
        json.dump(data, f, indent=4)


def removeToken(token: str):
    with open('tokens.txt', "r") as f:
        Tokens = f.read().split("\n")
        for t in Tokens:
            if len(t) < 5 or t == token:
                Tokens.remove(t)
        open("tokens.txt", "w").write("\n".join(Tokens))


def runBoostingProccess(invite: str, amount: int, expires: bool):
    if amount % 2 != 0:
        amount += 1

    tokens = get_all_tokens("tokens.txt")
    all_data = []
    tokens_checked = 0
    actually_valid = 0
    boosts_done = 0
    for token in tokens:
        s, headers = get_headers(token)
        profile = validate_token(s, headers)
        tokens_checked += 1

        if profile != False:
            actually_valid += 1
            data_piece = [s, token, headers, profile]
            all_data.append(data_piece)
            print(f"{Fore.LIGHTBLUE_EX}[16:01:20]{Fore.WHITE} [{Fore.YELLOW}❕{Fore.WHITE}] {Fore.YELLOW}{token} is Active ")
        else:
            pass
    for data in all_data:
        if boosts_done >= amount:
            return
        s, token, headers, profile = get_items(data)
        boost_data = s.get(f"https://discord.com/api/v9/users/@me/guilds/premium/subscription-slots", headers=headers)
        if boost_data.status_code == 200:
            if len(boost_data.json()) != 0:
                join_outcome, server_id = do_join_server(s, token, headers, profile, invite)
                if join_outcome:
                    for boost in boost_data.json():

                        if boosts_done >= amount:
                            removeToken(token)
                            if expires:
                                makeUsed(token)
                            return
                        boost_id = boost["id"]
                        bosted = do_boost(s, token, headers, profile, server_id, boost_id)
                        if bosted:
                            print(f"{Fore.LIGHTBLUE_EX}[16:01:20]{Fore.WHITE} [{Fore.YELLOW}❕{Fore.WHITE}] {Fore.GREEN} {token} Boosted ")
                            boosts_done += 1
                        else:
                            print(f"{Fore.CYAN} > {Fore.WHITE}{profile} {Fore.CYAN}ERROR BOOSTING {Fore.WHITE}{invite}")
                    removeToken(token)
                    if expires:
                        makeUsed(token)
                else:
                    print(f"{Fore.CYAN} > {Fore.WHITE}{profile} {Fore.CYAN}Cannot join {invite}")

            else:
                removeToken(token)
                print(f"{Fore.CYAN} > {Fore.WHITE}{profile} {Fore.CYAN}= Does not have Nitro")

@tasks.loop(seconds=1.0)
async def check_used():
    used = json.load(open("used.json"))
    toremove = []
    for token in used:
        print(token)
        if str(time.time()) >= used[token]["boostFinishAt"]:
            toremove.append(token)

    for token in toremove:
        used.pop(token)
        with open("tokens.txt", "a", encoding="utf-8") as file:
            file.write(f"{token}\n")
            file.close()

    json.dump(used, open("used.json", "w"), indent=4)


@bot.slash_command(guild_ids=[settings["guildID"]], name="license", description="License Someone...")
async def Admin(ctx: discord.ApplicationContext,
                    user: discord.Option(discord.Member, "Member to Admin", required=True)):
    if not isAdmin(ctx):
        return await ctx.respond("*You dont have permissions to do this, try buying this lol.*")

    settings["botAdminId"].append(str(user.id))
    json.dump(settings, open("settings.json", "w", encoding="utf-8"), indent=4)

    return await ctx.respond(f"*licensed {user.mention}*")



@bot.slash_command(guild_ids=[settings["guildID"]], name="stock", description="Allows you to see the current stock.")
async def stock(ctx: discord.ApplicationContext):
    return await ctx.respond(
        f"{len(open('tokens.txt', encoding='utf-8').read().splitlines())*2} Boost in stock")


@bot.slash_command(guild_ids=[settings["guildID"]], name="boost",
                   description="Boost Server")
async def boost(ctx: discord.ApplicationContext,
                invitecode: discord.Option(str, "invite..", required=True),
                amount: discord.Option(int, "amount..", required=True),
                days: discord.Option(int, "days..", required=True)):
    if not isAdmin(ctx):
        return await ctx.respond(
            embed=discord.Embed(title="🚫 | Access Denied", description="You dont have permissions to do this", color=0xff0000B)
        )

    if days != 30 and days != 90:

       await ctx.respond(f"Days are not between 30-90")

   
    await ctx.respond(f"Started boosting {amount}x's i think ")

    INVITE = invitecode.replace("//", "")
    if "/invite/" in INVITE:
        INVITE = INVITE.split("/invite/")[1]

    elif "/" in INVITE:
        INVITE = INVITE.split("/")[1]

    dataabotinvite = httpx.get(f"https://discord.com/api/v9/invites/{INVITE}").text

    if '{"message": "Unknown Invite", "code": 10006}' in dataabotinvite:
        print(f"{Fore.RED}{invite} is not a thing lmao ")
        return await ctx.edit(
            embed=discord.Embed(title="Error | Invite", description="Could not ", color=0xDE5BBB)
        )
    else:
        print(f"{Fore.LIGHTBLUE_EX}[16:01:20]{Fore.WHITE} [{Fore.YELLOW}❕{Fore.WHITE}] {Fore.YELLOW}{invitecode} {Fore.YELLOW}is Alive")

    EXP = True
    if days == 90:
        EXP = False

    runBoostingProccess(INVITE,amount, EXP)


    await ctx.respond(f"finsihed boosting {amount}x's i think")

def get_super_properties():
    properties = '''{"os":"Windows","browser":"Chrome","device":"","system_locale":"en-GB","browser_user_agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.54 Safari/537.36","browser_version":"95.0.4638.54","os_version":"10","referrer":"","referring_domain":"","referrer_current":"","referring_domain_current":"","release_channel":"stable","client_build_number":102113,"client_event_source":null}'''
    properties = base64.b64encode(properties.encode()).decode()
    return properties


def get_fingerprint(s):
    try:
        fingerprint = s.get(f"https://discord.com/api/v9/experiments", timeout=5).json()["fingerprint"]
        return fingerprint
    except Exception as e:
        # print(e)
        return "Error"


def get_cookies(s, url):
    try:
        cookieinfo = s.get(url, timeout=5).cookies
        dcf = str(cookieinfo).split('__dcfduid=')[1].split(' ')[0]
        sdc = str(cookieinfo).split('__sdcfduid=')[1].split(' ')[0]
        return dcf, sdc
    except:
        return "", ""


def get_proxy():
    return None  # can change if problems occur


def get_headers(token):
    while True:
        s = httpx.Client(proxies=get_proxy())
        dcf, sdc = get_cookies(s, "https://discord.com/")
        fingerprint = get_fingerprint(s)
        if fingerprint != "Error":  # Making sure i get both headers
            break

    super_properties = get_super_properties()
    headers = {
        'authority': 'discord.com',
        'method': 'POST',
        'path': '/api/v9/users/@me/channels',
        'scheme': 'https',
        'accept': '*/*',
        'accept-encoding': 'gzip, deflate',
        'accept-language': 'en-US',
        'authorization': token,
        'cookie': f'__dcfduid={dcf}; __sdcfduid={sdc}',
        'origin': 'https://discord.com',
        'sec-ch-ua': '"Google Chrome";v="95", "Chromium";v="95", ";Not A Brand";v="99"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/95.0.4638.54 Safari/537.36',

        'x-debug-options': 'bugReporterEnabled',
        'x-fingerprint': fingerprint,
        'x-super-properties': super_properties,
    }

    return s, headers


def find_token(token):
    if ':' in token:
        token_chosen = None
        tokensplit = token.split(":")
        for thing in tokensplit:
            if '@' not in thing and '.' in thing and len(
                    thing) > 30:  # trying to detect where the token is if a user pastes email:pass:token (and we dont know the order)
                token_chosen = thing
                break
        if token_chosen == None:
            print(f"Error finding token", Fore.RED)
            return None
        else:
            return token_chosen


    else:
        return token


def get_all_tokens(filename):
    all_tokens = []
    with open(filename, 'r') as f:
        for line in f.readlines():
            token = line.strip()
            token = find_token(token)
            if token != None:
                all_tokens.append(token)

    return all_tokens


def validate_token(s, headers):
    check = s.get(f"https://discord.com/api/v9/users/@me", headers=headers)

    if check.status_code == 200:
        profile_name = check.json()["username"]
        profile_discrim = check.json()["discriminator"]
        profile_of_user = f"{profile_name}#{profile_discrim}"
        return profile_of_user
    else:
        return False


def do_member_gate(s, token, headers, profile, invite, server_id):
    outcome = False
    try:
        member_gate = s.get(
            f"https://discord.com/api/v9/guilds/{server_id}/member-verification?with_guild=false&invite_code={invite}",
            headers=headers)
        if member_gate.status_code != 200:
            return outcome
        accept_rules_data = member_gate.json()
        accept_rules_data["response"] = "true"

        # del headers["content-length"] #= str(len(str(accept_rules_data))) #Had too many problems
        # del headers["content-type"] # = 'application/json'  ^^^^

        accept_member_gate = s.put(f"https://discord.com/api/v9/guilds/{server_id}/requests/@me", headers=headers,
                                   json=accept_rules_data)
        if accept_member_gate.status_code == 201:
            outcome = True

    except:
        pass

    return outcome


def do_join_server(s, token, headers, profile, invite):
    join_outcome = False;
    server_id = None
    try:
        # headers["content-length"] = str(len(str(server_join_data)))
        headers["content-type"] = 'application/json'

        for i in range(15):
            try:
                createTask = httpx.post("https://api.capmonster.cloud/createTask", json={
                    "clientKey": settings["capmonsterKey"],
                    "task": {
                        "type": "HCaptchaTaskProxyless",
                        "websiteURL": "https://discord.com/channels/@me",
                        "websiteKey": "76edd89a-a91d-4140-9591-ff311e104059"
                    }
                }).json()["taskId"]

                print(f"{Fore.LIGHTBLUE_EX}[16:01:20]{Fore.WHITE} [{Fore.YELLOW}❕{Fore.WHITE}] {Fore.YELLOW}Attemping to solve Captcha: [{createTask}]")

                getResults = {}
                getResults["status"] = "processing"
                while getResults["status"] == "processing":
                    getResults = httpx.post("https://api.capmonster.cloud/getTaskResult", json={
                        "clientKey": settings["capmonsterKey"],
                        "taskId": createTask
                    }).json()

                    time.sleep(1)

                solution = getResults["solution"]["gRecaptchaResponse"]

                print(f"{Fore.LIGHTBLUE_EX}[16:01:20]{Fore.WHITE} [{Fore.YELLOW}❕{Fore.WHITE}]{Fore.YELLOW} Successfully Solved Captcha: [{createTask}]")

                join_server = s.post(f"https://discord.com/api/v9/invites/{invite}", headers=headers, json={
                    "captcha_key": solution
                })

                break
            except:
                pass

        server_invite = invite
        if join_server.status_code == 200:
            join_outcome = True
            server_name = join_server.json()["guild"]["name"]
            server_id = join_server.json()["guild"]["id"]
            print(f"{Fore.LIGHTBLUE_EX}[16:01:20]{Fore.WHITE} [{Fore.YELLOW}❕{Fore.WHITE}] {Fore.YELLOW}{token} Attemping to Join Server ")
    except:
        pass

    return join_outcome, server_id


def do_boost(s, token, headers, profile, server_id, boost_id):
    boost_data = {"user_premium_guild_subscription_slot_ids": [f"{boost_id}"]}
    headers["content-length"] = str(len(str(boost_data)))
    headers["content-type"] = 'application/json'

    boosted = s.put(f"https://discord.com/api/v9/guilds/{server_id}/premium/subscriptions", json=boost_data,
                    headers=headers)
    if boosted.status_code == 201:
        return True
    else:
        return False


def get_invite():
    while True:
        print(f"{Fore.CYAN}Server invite?", end="")
        invite = input(" > ").replace("//", "")

        if "/invite/" in invite:
            invite = invite.split("/invite/")[1]

        elif "/" in invite:
            invite = invite.split("/")[1]

        dataabotinvite = httpx.get(f"https://discord.com/api/v9/invites/{invite}").text

        if '{"message": "Unknown Invite", "code": 10006}' in dataabotinvite:
            print(f"{Fore.YELLOW} Could not Start Task")
        else:
            print(f"{Fore.CYAN} Starting Task")
            break

    return invite


def get_items(item):
    s = item[0]
    token = item[1]
    headers = item[2]
    profile = item[3]
    return s, token, headers, profile


@bot.event
async def on_ready():
    activity = discord.Game(name="", type=2)
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.competing, name="", status=discord.Status.online))
    print(f"{Fore.MAGENTA}                     __ _____________ __  ___  ____  ____  __________")
    print(f"{Fore.MAGENTA}                    / // /  _/ ___/ // / / _ )/ __ \/ __ \/ __/_  __/")
    print(f"{Fore.MAGENTA}                   / _  // // (_ / _  / / _  / /_/ / /_/ /\ \  / /   ")
    print(f"{Fore.MAGENTA}                  /_//_/___/\___/_//_/ /____/\____/\____/___/ /_/    ")
    print(f"{Fore.MAGENTA}                 ")
    print(f"{Fore.MAGENTA}")
    print(f"{Fore.MAGENTA}")                                     
bot.run(settings["botToken"])                          
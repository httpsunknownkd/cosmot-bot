import os
import json
import time
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
import aiohttp
import random
import asyncio
import discord
from discord.ext import commands, tasks
from typing import cast, Optional, Dict
from discord import TextChannel
from keep_alive import keep_alive

# --- Config ---

MESSAGE_XP_FIXED = 2
MESSAGE_XP_COOLDOWN_SEC = 30        # Per-user anti-spam cooldown

REACTION_XP = 1
REACTION_XP_COOLDOWN_SEC = 30       # Per-user anti-spam cooldown

VC_XP_PER_MINUTE_ON_LEAVE = 0.25    # When session ends
VC_HEARTBEAT_INTERVAL_SEC = 300     # 5 minutes
VC_HEARTBEAT_XP = 0.5
VC_XP_COOLDOWN_SEC = 300# Every heartbeat if still in VC

AUTOSAVE_MINUTES = 10

VERBOSE_LOGS = False                # flip to True if you need spammy prints

# --- XP computation function ---
def compute_message_xp(message, profile):
    now = int(time.time())
    last_award = profile.get("last_msg_xp", 0)
    if now - last_award < MESSAGE_XP_COOLDOWN_SEC:
        return 0

    xp = MESSAGE_XP_FIXED
    profile["last_msg_xp"] = now
    return xp
        
# --- Intents Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True  # REQUIRED for on_member_join

bot = commands.Bot(command_prefix='!', intents=intents)

last_sabaw_line = None
last_sabaw_intro = None

VERIFY_ROLE_NAME = "certified tambayers ⋆ ˙ ⟡ .ᐟ"
WELCOME_CHANNEL_ID = 1293515009665531925    
BOOST_ROLE_NAME = "booster ⋆ ˙ ⟡ .ᐟ"

# --- State ---

xp_data: Dict[str, Dict[str, dict]] = {}
vc_sessions: Dict[str, dict] = {}

# Per-user cooldown trackers
message_cooldowns: Dict[int, float] = {}
reaction_cooldowns: Dict[int, float] = {}

# --- Load or Initialize XP Data ---
XP_FILE = "xp_data.json"

if os.path.exists(XP_FILE):
    try:
        with open(XP_FILE, "r") as f:
            xp_data = json.load(f)
    except Exception as e:
        print(f"❌ Failed to load XP data, starting fresh: {e}")
        xp_data = {}
else:
    xp_data = {}

# --- Save XP Data ---
def save_xp():
    try:
        with open(XP_FILE, "w") as f:
            json.dump(xp_data, f, indent=4)
        # Backup
        with open("xp_data_backup.json", "w") as backup:
            json.dump(xp_data, backup, indent=4)
    except Exception as e:
        print(f"❌ Failed to save XP data: {e}")

# --- Auto Save XP every few minutes ---
@tasks.loop(minutes=10)
async def autosave_xp():
    print("💾 Auto-saving XP data...")
    save_xp()

# --- Ensure XP Profile Exists ---
def ensure_xp_profile(guild_id, user_id):
    if guild_id not in xp_data:
        xp_data[guild_id] = {}
    if user_id not in xp_data[guild_id]:
        xp_data[guild_id][user_id] = {
            "xp": 0,
            "level": 1,
            "last_activity": 0,
            "daily_streak": 0,
            "streak_day": 1,
            "breakdown": {
                "chat": 0,
                "reaction": 0,
                "vc": 0
            }
        }
    
# --- Bot Ready ---
@bot.event
async def on_ready():
    print(f"🚨 Bot is ready: {bot.user} | ID: {bot.user.id}")
    bot.add_view(VerifyButton())

    for guild in bot.guilds:
        for vc in guild.voice_channels:
            for member in vc.members:
                if member.bot:
                    continue

                user_id = str(member.id)
                guild_id = str(guild.id)

                ensure_xp_profile(guild_id, user_id)
                vc_sessions[user_id] = {
                    "start_time": asyncio.get_event_loop().time(),
                    "channel": vc
                }

                if VERBOSE_LOGS:
                    print(f"✅ Tracking VC session for {member.display_name} at startup.")

    if not autosave_xp.is_running():
        autosave_xp.start()
        print("💾 Autosave loop started.")

    if not track_vc_duration.is_running():
        track_vc_duration.start()
        print("⏳ VC XP loop started.")

# --- Parsing Helpers ---
def parse_announcement_input(input_str):
    parts = [part.strip() for part in input_str.split('|')]

    # No pipes = just message body
    if len(parts) == 1:
        return [], "", parts[0], ""

    while len(parts) < 4:
        parts.append("")

    emoji_part, title, body, image_url = parts
    emojis = emoji_part.split()
    return emojis, title, body, image_url
    
# --- Welcome Event Handler ---
@bot.event
async def on_member_join(member):
    channel = bot.get_channel(WELCOME_CHANNEL_ID)
    channel = cast(TextChannel, channel)
    
    if channel:
        embed = discord.Embed(
            title="🛋️   ♯ 𝗯𝗮𝗸𝗶𝘁 𝗽𝗮𝗿𝗮𝗻𝗴 𝗸𝗮𝗯𝗮𝗱𝗼 𝗮𝗸𝗼 𝘀𝗮 𝗯𝗮𝗴𝗼  .ᐟ",
            description=(
                f"ayan na si {member.mention} — just crash-landed into **⧼ 𝘀𝗮𝗯𝗮𝘄 𝗵𝘂𝗯 ⧽ ⋆ ˙ ⟡ .ᐟ** 🍜\n\n"
                " before you dive face-first into the weird soup we call comms, scoop up your roles in <#1396943702085206117> "
                "this place is full of late-night rants, unhinged kwento, and occasional emotional damage (all wholesome tho).\n\n"
                "we don’t bite unless it’s a joke. welcome to the chaos corner — tambay responsibly! 🛁"
            ),
            color=discord.Color.from_str("#E75480")
        )
        banner_url = "https://drive.google.com/uc?export=view&id=1XQ-wPqW6L-DUgnXLIIJiXng_ovEW9pQ4"
        embed.set_image(url=banner_url)
        await channel.send(embed=embed)

# --- Verify Button View ---
class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="slurp in!", style=discord.ButtonStyle.success, emoji="🍜", custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("❌ This button only works in servers!", ephemeral=True)
            return

        member = guild.get_member(interaction.user.id)
        if member is None:
            await interaction.response.send_message("❌ Couldn’t fetch your member data!", ephemeral=True)
            return

        role = discord.utils.get(guild.roles, name=VERIFY_ROLE_NAME)
        if role is None:
            await interaction.response.send_message("⚠️ Couldn't find the verify role!", ephemeral=True)
            return

        if role in member.roles:
            await interaction.response.send_message("you're already part of the sabaw! 🍜", ephemeral=True)
        else:
            await member.add_roles(role)
            await interaction.response.send_message("🍜 welcome to the hub — you’re in!", ephemeral=True)

# --- Admin-Only: Send Verification Embed ---
@bot.command(name="sendverify")
@commands.has_permissions(administrator=True)
async def send_verify_message(ctx):
    await ctx.message.delete()
    embed = discord.Embed(
        title="🛋️   ♯ 𝗼𝗵 𝗵𝗲𝗹𝗹𝗼 𝘁𝗵𝗲𝗿𝗲, 𝘆𝗼𝘂 𝗺𝗮𝗱𝗲 𝗶𝘁  .ᐟ",
        description=(
            "before you dive into the sabaw and explore the rest of the server, slide over to <#1396943702085206117> and grab your roles. "
            "done? sweet. now bop the button below to verify and unlock the rest of the chaos. we’re kinda weird but we’re nice. "
            "we’re happy you’re here — welcome to the hub, tambayers! 🍜"
        ),
        color=discord.Color.from_str("#E75480")
    )
    await ctx.send(embed=embed, view=VerifyButton())

# --- Booster Spotted ---
@bot.event 
async def on_member_update(before, after):
    if not before.premium_since and after.premium_since:
        channel = bot.get_channel(1397335182465437697)
        if not isinstance(channel, TextChannel):
            print("❌ Boost channel not found or wrong type.")
            return
            
        booster_role_name = "booster ⋆ ˙ ⟡ .ᐟ"
        booster_role = discord.utils.get(after.guild.roles, name=booster_role_name)

        if booster_role:
            await after.add_roles(booster_role)

        embed = discord.Embed(
            title="🍜 ♯ 𝘀𝗮𝗯𝗮𝘄 𝘁𝗼𝗽-𝘂𝗽 𝗿𝗲𝗰𝗲𝗶𝘃𝗲𝗱 .ᐟ",
            description=(
                f"{after.mention} just boosted the server like it’s a sugar daddy simulator. 💸 "
                " your generosity is unmatched and for that, we offer... nothing but vibes, emotional damage, and maybe a noodle? hehe. thank u po! 🍜"
            ),
            color=discord.Color.from_str("#E75480")
        )
        banner_url = "https://drive.google.com/uc?export=view&id=1EiqxDE1P2GpbHMSab6pWAZwNkwvGprN_"
        embed.set_image(url=banner_url)
        embed.set_footer(text="your sparkle is now tax-deductible (not really)")
        await channel.send(embed=embed)

# --- Leaver ---
@bot.event
async def on_member_remove(member):
    channel = bot.get_channel(1293513854466261064)

    if not isinstance(channel, TextChannel):
        print("❌ Goodbye channel not found or is not a TextChannel.")
        return
        
    goodbye_lines = [
        f"{member.name} has rage quit the sabaw simulator 💔",
        f"{member.name} has evaporated from the server like 3AM tears.",
        f"{member.name} left... but did they ever truly arrive?",
        f"{member.name} dipped faster than a dodged ranked match 😔",
        f"{member.name} has vanished. We checked the CCTV. Nothing. Gone.",
        f"{member.name} said 'brb' and never returned 💀",
        f"{member.name} was last seen vibing. now? unfriended by God."
    ]

    embed = discord.Embed(
        title="📦 ♯ 𝗲𝘅𝗶𝘁 𝗹𝗼𝗴 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗲𝗱 .ᐟ",
        description=random.choice(goodbye_lines),
        color=discord.Color.from_str("#E75480")
    )
    banner_url = "https://drive.google.com/uc?export=view&id=18vPUEokfGDT6npjjFCjJMKYRLy3J4UZu"
    embed.set_image(url=banner_url)
    embed.set_footer(text="one less sabog in the server. 😔🕊️")
    await channel.send(embed=embed)
    
# --- Commands ---
@bot.command(name="ann")
async def announce(ctx, *, input_message: str):
    await ctx.message.delete()

    try:
        emojis, title, body, image_url = parse_announcement_input(input_message)

        if not title and not body and not image_url and not ctx.message.attachments:
            await ctx.send("⚠️ You need at least a title, message, image, or emoji.")
            return

        ## Fallback for image
        image_url = None
        if ctx.message.attachments:
            attachment = ctx.message.attachments[0]
            print("📎 Attachment found:", attachment.filename)
            print("📷 Content type:", attachment.content_type)

            if attachment.content_type and attachment.content_type.startswith("image/"):
                image_url = attachment.proxy_url  # important for Replit/CDN access

        # Embed Creation
        embed = discord.Embed(
            title=title if title else None,
            description=body or "*No message provided.*",
            color=discord.Color.from_str("#E75480")
        )

        if image_url:
            embed.set_image(url=image_url)
            print("🖼️ Embed image set to:", image_url)
        else:
            print("⚠️ No valid image found in attachment.")

        # Send embed
        sent = await ctx.send(content="@everyone", embed=embed)

        # ➕ Add emoji reactions
        for emoji in emojis:
            try:
                await sent.add_reaction(emoji)
                await asyncio.sleep(0.3)
            except discord.HTTPException:
                if VERBOSE_LOGS:
                    print(f"❌ Couldn't add emoji: {emoji}")

    except Exception as e:
        await ctx.send("⚠️ Something went wrong formatting your announcement.")
        print("‼️ ANN ERROR:", e)

@bot.command(name="say")
@commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
async def say_plain(ctx, *, message):
    emojis, text, title, image_url = parse_announcement_input(message)

    # 🗣️ Send plain text (fallback to title or body)
    content = text or title or "*No message provided.*"
    sent = await ctx.send(content.strip())

    # ➕ React with any parsed emojis
    for emoji in emojis:
        try:
            await sent.add_reaction(emoji)
            await asyncio.sleep(0.3)
        except discord.HTTPException:
            if VERBOSE_LOGS:
                print(f"⚠️ Could not add emoji: {emoji}")
# Cooldown error handler
@announce.error
async def announce_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")
        
# --- Boosters ---
@bot.command(name="boosters")
async def boosters(ctx):
    await ctx.message.delete()
    boosters = [member.mention for member in ctx.guild.members if member.premium_since]

    if boosters_list:
        listed = "\n".join([f"{i+1}. {mention}" for i, mention in enumerate(boosters)])
        description = (
            "behold... the chosen few who willingly gave discord their wallet and their soul — just so we can spam vc at 3am and post brainrot in HD.\n\n"
            "they didn’t just boost the server, they boosted their rizz level by +69. "
            "they’re the reason the vibes are high, the server is alive, and your ping is probably still bad but prettier somehow.\n\n"
            "kneel before the sabaw elite 🍜 :\n\n"
            + listed
        )
    else:
        description = "🚫 no boosters... sabaw is running on vibes alone. 😔"

    embed = discord.Embed(
        title="🛋️ ♯ 𝘀𝗮𝗯𝗮𝘄 𝘀𝘂𝗴𝗮𝗿 𝗿𝗼𝗹𝗹-𝗰𝗮𝗹𝗹 .ᐟ",
        description=description,
        color=discord.Color.from_str("#E75480")
        )

    embed.set_image(url="https://drive.google.com/uc?export=view&id=1EiqxDE1P2GpbHMSab6pWAZwNkwvGprN_")
    embed.set_footer(text="these boosters boiled in the sabaw — now they season the soup. 🍥")
    await ctx.send(embed=embed)
    
# --- Test Drive ---
@bot.command(name="huy")
@commands.cooldown(rate=1, per=30, type=commands.BucketType.user) 
async def test_bot(ctx):
    thinking = await ctx.send("🤖 checking if bot is breathing...")
    await asyncio.sleep(1.2)
    await thinking.edit(content="🧠 analyzing braincells... please wait...")
    await asyncio.sleep(1.5)
    latency = round(bot.latency * 1000)

    responses = [
        f"huy din 😐 buhay pa ako, unfortunately.\n`latency: {latency}ms`",
        f"ano na? gising naman ako ah 😒\n`lag check: {latency}ms`",
        f"gising ako pero not mentally present 😭\n`latency: {latency}ms`",
        f"you called? chismis ba ‘to or actual emergency?\n`ping: {latency}ms`",
        f"yes? i’m up. barely. what now.\n`slay level: {latency}ms`"
    ]

    await asyncio.sleep(1)
    await thinking.edit(content=random.choice(responses))
    
@announce.error
async def announce_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")
        
# --- Random Interactive Command ---
@bot.command(name="sabaw")
@commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
async def sabaw_line(ctx):
    global last_sabaw_line
    global last_sabaw_intro
    
    intro_lines = [
        "🤖 sabaw detected. initiating delulu.exe...",
        "🎧 queueing chaos with no warmup as usual...",
        "⚠️ brain ping: 999ms",
        "👾 booting up sabaw gaming core...",
        "📉 IQ dropping… please wait.",
        "🎮 controller disconnected — like my sense of purpose.",
    ]

    sabaw_lines = [
        "sleep? coping lang yan",
        "bakit pa tayo naglalaro sa compe kung malulugmok din tayo?",
        "akala ko ace ako, turns out hallucination lang pala.",
        "wala akong kill, pero ang dami kong presence 😌",
        "i don't bottom frag, i just collect deaths aesthetically.",
        "every round is a warmup round if you gaslight hard enough.",
        "‘one more game’ daw, 5AM na ghorl.",
        "my aim? like my mental health — shaky and unpredictable.",
        "‘lag ako’ is my favorite excuse, even when i’m not playing.",
        "they said ‘diff,’ but baby i’m the lore.",
        "i flash myself more than the enemy. self-love yan.",
        "i main chaos. not the agent — the lifestyle.",
        "rank is just a number. delulu is the meta.",
        "akala ko clutch moment... turns out spectator mode agad.",
        "diff daw? bro, i’m the plot twist, not the problem.",
        "kalaban may comms, kami may trauma bonding.",
        "teamfight? i was just sightseeing 😌",
        "‘push B’ pero ang pinush ko boundaries.",
        "support ako, pero emotionally lang.",
        "wala akong crosshair control pero meron akong comedic timing.",
        "my build is bad but my fit is cute, so who’s really winning?",
        "i topfrag when no one’s watching. fr.",
        "AFK ako pero spiritually present.",
        "carry me? i’m heavy emotionally, good luck.",
        "sino MVP? emotional vulnerability and inconsistent aim.",
        "voice chat off for my own safety and yours.",
        "griefing? no, i’m just ✨ improvising ✨",
        "kung may baril ka sa valo, ako may delulu sa discord.",
        "ult ko ready, pero courage ko hindi.",
        "tactical feeding lang to maintain balance.",
        "strat? i follow vibes not calls.",
        "rank reset? good. now i can disappoint a fresh batch of teammates.",
        "clutch or cry. minsan both.",
        "vc na pero di ako magsasalita, presence lang po.",
        "server muted pero emotionally invested.",
        "nag-join ako for vibes, not conversations.",
        "pumasok lang ako para mag-leave ulit. ganon ako ka-loyal.",
        "my mic is broken... along with my will to socialize.",
        "discord is my therapy but everyone’s equally unstable.",
        "wala akong ambag pero ang aesthetic ng role ko diba?",
        "nakikinig lang ako, pero di ko rin gets.",
        "status: online, mindset: offline.",
        "di ako active pero di rin ako nawawala. mysterious lang.",
        "caught typing then overthinking... backspaced everything.",
        "lahat kayo nag chachat, ako lang nagrereact ng 🫡",
        "kung may verification, sana may validation din 🥲",
        "joined for the emotes, stayed for the sabog energy.",
        "i log into discord just to stare at channels and leave.",
        "active ako sa utak niyo, hindi sa chat.",
        "nag-join ako ng VC pero background noise lang ako. literally.",
        "di ako nagrereply pero i feel things deeply.",
        "my discord role carries more weight than my life choices.",
        "sabog ako IRL, kaya sabaw din sa server. balance lang."
]

    # random intro + sabaw line combo
    intro = random.choice(intro_lines)
    while intro == last_sabaw_intro:
        intro = random.choice(intro_lines)
    last_sabaw_intro = intro
    
    sabaw = random.choice(sabaw_lines)
    while sabaw == last_sabaw_line:
        sabaw = random.choice(sabaw_lines)
    last_sabaw_line = sabaw
        
    # dramatic sabaw bot loading
    thinking = await ctx.send("🤖 diagnosing emotional damage...")
    await asyncio.sleep(1.2)
    await thinking.edit(content="🩻 calculating iq deficit... please wait...")
    await asyncio.sleep(1.5)
    await thinking.edit(content=intro)
    await ctx.send(f"> {sabaw}")

@announce.error
async def announce_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")
        
@bot.command(name="who")
@commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
async def who(ctx):
    online_members = [
        m for m in ctx.guild.members
        if not m.bot and m.status in [discord.Status.online, discord.Status.idle, discord.Status.dnd]
        ]

    if not online_members:
        await ctx.send("no one is online... just you and your thoughts. 💭")
        return

    chosen = random.choice(online_members)
        
    roast_lines = [
        f"🔍 hmm... today we blame: {chosen.mention}",
        f"🧠 ang sabaw ngayong gabi: {chosen.mention}",
        f"🎯 target acquired: {chosen.mention}. alam mo na gagawin mo.",
        f"📣 {chosen.mention} has been selected as tribute.",
        f"🍵 magpaliwanag ka {chosen.mention}, dami mong chismis.",
        f"🎤 {chosen.mention} you're mic'ing up or mic'ing down?",
        f"🚨 blame report filed against {chosen.mention}. based on vibes lang.",
        f"🔮 psychic visions point to... {chosen.mention}. bakit parang may atraso?",
        f"🤨 bakit si {chosen.mention}? wala lang. feels right.",
        f"🍜 sabaw detector beeped at {chosen.mention} — pakisalo na sa VC.",
        f"📡 detecting high sabaw levels from {chosen.mention}... suspicious.",
        f"📸 caught {chosen.display_name} lacking. screenshot mo na yan.",
        f"🚨 {chosen.display_name} just got exposed. for what? yes.",
        f"🗣️ rumor has it {chosen.mention} knows the lore and isn't telling.",
        f"🎲 fate rolled and it's {chosen.mention}. good luck ig.",
        f"🧃 hydration check: {chosen.mention} is 90% sabaw today.",
        f"🧙‍♂️ legend says {chosen.mention} caused the chaos in gen chat.",
        f"🎬 {chosen.mention} has main character energy... for better or worse.",
        f"🕵️‍♀️ {chosen.display_name} is definitely up to something sus. we’re watching.",
        f"🦶 caught {chosen.display_name} typing with their toes. again.",
        f"📖 if {chosen.mention} isn’t part of the lore, they are now. canon na 'yan.",
    ]
    
    await ctx.send(random.choice(roast_lines))

@announce.error
async def announce_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")
        
@bot.command(name="roast")
@commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
async def roast(ctx, member: Optional[discord.Member] = None):
    target = member or ctx.author

    roasts = [
        f"{target.mention}, you're the reason FF is a strat in this server.",
        f"{target.mention} plays like their mouse is underwater.",
        f"{target.mention}, you lag even in real life.",
        f"{target.mention} got aim like a stormtrooper on caffeine withdrawal.",
        f"{target.mention} flashes teammates more than enemies.",
        f"{target.mention} is the type to ask for heals as Reyna.",
        f"{target.mention} camped in VC for 2 hours and said nothing but 'lag ako'.",
        f"{target.mention} tried to IGL but forgot where A site was.",
        f"{target.mention} types 'DC' every time they lose a duel.",
        f"{target.mention} ulted... for what? dramatic effect?",
        f"{target.mention} thought clutch meant clutch bag.",
        f"{target.mention} is one Q away from uninstalling.",
        f"{target.mention} has aim assist… and still misses.",
        f"{target.mention}, your crosshair said 'not my job'.",
        f"{target.mention} talks trash, plays compost.",
        f"{target.mention}, if L’s were currency, you'd be a millionaire.",
        f"{target.mention}, you're basically a mobile hotspot—hot but laggy.",
        f"{target.mention} joins VC just to breathe and disconnect.",
        f"{target.mention}, you peek like you’ve got plot armor. You don’t.",
        f"{target.mention}, your KD ratio hurt my feelings.",
        f"{target.mention}, you're built like a bronze rank meme.",
        f"{target.mention}, your main role is comedic relief.",
        f"{target.mention}, you'd top frag in a lobby of bots. Maybe.",
        f"{target.mention} has more tech issues than NASA in the '60s.",
        f"{target.mention} is still waiting for ping to stabilize… from last week.",
        f"{target.mention} couldn’t clutch if their life was a zip file.",
        f"{target.mention} got banned from spike planting for emotional damage.",
        f"{target.mention}, when you play, the game uninstalls itself.",
        f"{target.mention} gets flashed by the loading screen.",
        f"{target.mention}, your game sense has left the chat.",
        f"{target.mention}, your brain's still on patch 1.0.",
        f"{target.mention}, how are you still bronze with that much delusion?",
        f"{target.mention} has one good game every blood moon.",
        f"{target.mention} has more excuses than wins.",
        f"{target.mention}, your DPI is short for 'Don’t Play, Idiot'.",
        f"{target.mention} moves like they’re playing via Google Docs.",
        f"{target.mention}, I’ve seen AFKs with better map awareness.",
        f"{target.mention}, you’re the NPC that spams 'gg' at round 3.",
        f"{target.mention} builds character, not stats.",
        f"{target.mention} plays like a motivational arc for their enemies.",
        f"{target.mention} thought 'eco round' meant economy is down IRL.",
        f"{target.mention} speedruns L’s like it’s a category on Twitch.",
        f"{target.mention} says “one more?” then drops 2 kills in 12 rounds.",
        f"{target.mention} got reported for griefing by the matchmaking system itself.",
        f"{target.mention}, even bots call you free kills.",
        f"{target.mention}, you don't miss—because you don't shoot.",
        f"{target.mention} got less map presence than a smoke in spawn.",
        f"{target.mention} is playing peek-a-boo in Valorant and still loses.",
        f"{target.mention} got the reaction time of a sleepy toaster.",
        f"{target.mention}, your role in Discord is comic relief.",
        f"{target.mention} been typing “hi” in general for 3 months, never said a word in VC.",
        f"{target.mention} joins calls just to lag out dramatically.",
        f"{target.mention} posts like they’re being monitored by DepEd.",
        f"{target.mention}, you exist in the server like a haunted ping.",
    ]

    await ctx.send(random.choice(roasts))

@announce.error
async def announce_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")
        
# --- Message for XP Tracking ---
@bot.event
async def on_message(message):
    if message.author.bot or message.guild is None:
        return
        
    # 🧪 DEBUG PRINT
    if VERBOSE_LOGS:
        print("Message received from", message.author, "| Content:", message.content[:80])

    guild_id = str(message.guild.id)
    user_id = str(message.author.id)
    ensure_xp_profile(guild_id, user_id)
    profile = xp_data[guild_id][user_id]

    gained_xp = compute_message_xp(message, profile)

    now = int(time.time())
        
    last_activity = profile.get("last_activity", 0)
    if now - last_activity >= 86400 and now - last_activity < 172800:
        profile["streak_day"] += 1
        profile["xp"] += DAILY_STREAK_BONUS
    elif now - last_activity >= 172800:
        profile["streak_day"] = 1
    profile["last_activity"] = now

    profile["xp"] += gained_xp
    profile["breakdown"]["chat"] += gained_xp

    # --- Level Up Check ---
    level = profile["level"]
    xp    = profile["xp"]
    next_level_xp = level * 100

    if xp >= next_level_xp:
        profile["level"] += 1
        new_level = profile["level"]

        guild = message.guild
        member = message.author

        # 📢 Choose the level-up channel or fallback
        levelup_channel = bot.get_channel(1397335102266277909)
        if not levelup_channel:
            print("⚠️ Level-up channel not found. Defaulting to message.channel")
            levelup_channel = message.channel
        
        unhinged_level_ups = [
            f"💥  {message.author.mention} leveled up to **Level {new_level}**! still no skills but now with more vibes.",
            f"🎉  {message.author.mention} ascended to **Level {new_level}** — braincells not included.",
            f"📈  sabaw pressure rising... {message.author.mention} just hit **Level {new_level}**.",
            f"🥳  **Level {new_level}** achieved by {message.author.mention}! may XP ka pero may peace ka ba?",
            f"🔫  {message.author.mention} just leveled up to **Level {new_level}**. top frag in trauma!",
            f"🧠  {message.author.mention} reached **Level {new_level}**... allegedly smarter now, but sources say delulu pa rin.",
            f"🚀  {message.author.mention} hit **Level {new_level}**! rank up powered by caffeine, chaos, and zero strategy.",
            f"🌀  **{new_level}** na siya?! {message.author.mention}, come outside we just wanna talk 💀",
            f"✨  {message.author.mention} leveled up! reward: existential dread at Level {new_level}.",
            f"👻  {message.author.mention} hit **Level {new_level}**. baka this is your villain arc.",
            f"🫠  {message.author.mention} hit **Level {new_level}**! achievements unlocked: social battery drained.",
            f"📉  Level {new_level}? {message.author.mention} now officially too tired to be humble.",
            f"😵‍💫  {message.author.mention} just hit **Level {new_level}** — performance powered by caffeine and 2 hours of sleep.",
            f"🎭  new level, same clownery. {message.author.mention} reached **Level {new_level}**!",
            f"🧃  {message.author.mention} is now **Level {new_level}**. emotionally hydrated but mentally absent.",
            f"🎮  {message.author.mention} ranked up... and still has no idea what’s going on. Level {new_level} achieved!",
            f"💔  Level {new_level}?! {message.author.mention} you need to log off and touch grass.",
            f"🌌  {message.author.mention} transcended to **Level {new_level}**. in space, no one can hear your breakdown.",
            f"📺  {message.author.mention} unlocked **Level {new_level}** and accidentally subscribed to character development.",
            f"🛌  Level {new_level} reached while everyone else was asleep. go touch pillow, {message.author.mention}.",
            f"💀  {message.author.mention} leveled up again. at this point, we fear their power. **Level {new_level}**!",
            f"🪫  {message.author.mention} at **Level {new_level}**: zero motivation, maximum XP.",
            f"🍵  Level {new_level} and still spilling tea mid-fight. iconic behavior, {message.author.mention}.",
            f"🫃  {message.author.mention} pregnant with XP. welcome to **Level {new_level}**.",
        ]

        try: 
            if banner:
                if isinstance(levelup_channel, discord.abc.Messageable):
                    await levelup_channel.send(file=banner)
                else:
                    print("⚠️ levelup_channel is not messageable.")                
            else:
                if isinstance(levelup_channel, discord.abc.Messageable):
                    await levelup_channel.send(random.choice(unhinged_level_ups))
                else:
                    print("⚠️ levelup_channel is not messageable.")
        except Exception as e:
            print(f"⚠️ Banner error: {e}")
            if isinstance(levelup_channel, discord.abc.Messageable):
                        await levelup_channel.send(random.choice(unhinged_level_ups))

    save_xp()
    await bot.process_commands(message)
    print("Command processing triggered")

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return

    if reaction.message.guild is None:
        print("⚠️ Reaction came from a DM. Ignoring.")
        return
        
    guild_id = str(reaction.message.guild.id)
    user_id = str(user.id)

    ensure_xp_profile(guild_id, user_id)
    profile = xp_data[guild_id][user_id]

    now = int(time.time())
    
    # --- Cooldown check ---
    last_react_time = profile.get("last_react_xp_time", 0)
    if now - last_react_time < REACTION_XP_COOLDOWN_SEC:
        print(f"⏱️ {user.name} reaction XP cooldown: {REACTION_XP_COOLDOWN_SEC - (now - last_react_time)}s left")
        return  # Still on cooldown → no XP

    profile["last_react_xp_time"] = now

    # --- Award XP ---
    profile["xp"] += REACTION_XP
    
    if "breakdown" not in profile:
        profile["breakdown"] = {}
    if "reaction" not in profile["breakdown"]:
        profile["breakdown"]["reaction"] = 0

    profile["breakdown"]["reaction"] += REACTION_XP
    save_xp()

    print(f"🔁 +{REACTION_XP} XP from reaction by {user.name} in {reaction.message.channel.name}")
    
# --- VC Join/Leave Tracking ---
@bot.event
async def on_voice_state_update(member, before, after):
    if member.bot:
        return
        
    guild_id = str(member.guild.id)
    user_id = str(member.id)
    ensure_xp_profile(guild_id, user_id)

    # Make sure this prints!
    if after.channel and not before.channel:
        print(f"{member.name} joined VC! tracking session time now...")

        # ✅ This should happen:
        vc_sessions[user_id] = {
            "start_time": asyncio.get_event_loop().time(),
            "channel": after.channel
        }
        
    # Left VC
    elif before.channel and not after.channel:
        if user_id in vc_sessions:
            session = vc_sessions.pop(user_id)
            join_time = session["start_time"]
            duration = int(asyncio.get_event_loop().time() - join_time)
            xp_earned = duration // 60

            if xp_earned > 0:
                xp_data[guild_id][user_id]["xp"] += xp_earned
 
                if "breakdown" not in xp_data[guild_id][user_id]:
                    xp_data[guild_id][user_id]["breakdown"] = {}
                if "vc" not in xp_data[guild_id][user_id]["breakdown"]:
                    xp_data[guild_id][user_id]["breakdown"]["vc"] = 0

                xp_data[guild_id][user_id]["breakdown"]["vc"] += xp_earned
                save_xp()

                print(f"🎧 {member.name} left VC after {duration}s → earned {xp_earned} XP")
            else:
                print(f"⏱️ {member.name} was in VC too short to earn XP.")

# --- Track VC Duration ---
@tasks.loop(seconds=300)
async def track_vc_duration():
    now = asyncio.get_event_loop().time()

    for user_id, session in vc_sessions.items():
        guild = session["channel"].guild
        guild_id = str(guild.id)

        ensure_xp_profile(guild_id, user_id)
        profile = xp_data[guild_id][user_id]
        
        # --- Cooldown check ---
        last_vc_xp_time = profile.get("last_vc_xp_time", 0)
        if now - last_vc_xp_time < VC_XP_COOLDOWN_SEC:
            remaining = int(VC_XP_COOLDOWN_SEC - (now - last_vc_xp_time))
            print(f"⏱️ Skipping VC XP for {guild.get_member(int(user_id)).display_name}, {remaining}s left on cooldown.")
            continue

        # --- Award XP ---
        xp_earned = 0.5
        profile["xp"] += xp_earned
        profile["last_vc_xp_time"] = now

        if "breakdown" not in profile:
            profile["breakdown"] = {}
        if "vc" not in profile["breakdown"]:
            profile["breakdown"]["vc"] = 0
        profile["breakdown"]["vc"] += xp_earned
        
        save_xp()

        member = guild.get_member(int(user_id))
        if member:
            elapsed = int(now - session["start_time"])
            print(f"🕐 {member.display_name} is still in VC ({elapsed}s) → awarded +{xp_earned} XP")

# --- Command: VC Stats ---
@bot.command(name="vcstats")
@commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
async def vcstats(ctx, member: Optional[discord.Member] = None):
    member = member or ctx.author
    voice_state = member.voice

    if not voice_state or not voice_state.channel:
        embed = discord.Embed(
            title="🔍 ♯ 𝘃𝗰 𝘀𝗻𝗼𝗼𝗽 𝗿𝗲𝗽𝗼𝗿𝘁  .ᐟ",
            description=f"{member.mention} is currently **not in a vc**.\n\n📉 **status**: ghosting the squad??\n🧘‍♀️ *mood**: mysterious + lowkey AF\n\njoin a vc before your XP cries itself to sleep 😴",
            color=discord.Color.from_str("#E75480")
        )
        await ctx.send(embed=embed)
        return

    user_id = str(member.id)
    channel = voice_state.channel

    print("vc_sessions:", vc_sessions)
    print("looking for user_id:", user_id)
    
    if user_id in vc_sessions:
        session = vc_sessions[user_id]
        start_time = session["start_time"]
        duration = int(asyncio.get_event_loop().time() - start_time)
        minutes, seconds = divmod(duration, 60)

        funny_comments = [
            "🔄  probably overthinking, possibly vibing.",
            "📡  vc spirit detected... but are they even talking?",
            "🧠  braincells: questionable, vibes: immaculate.",
            "🎤  might be podcasting. might be trauma dumping.",
            "🍵  just here for the chismis tbh.",
            "🔊  background noise main character.",
            "📞  in a vc but emotionally elsewhere.",
            "🚪  hasn’t said a word in 45 minutes. still slaying.",
            "🫠  mic muted, soul screaming.",
            "🎙️  one sentence away from oversharing.",
            "🧃  probably drinking iced coffee or matcha at 1AM.",
            "📚  lore dump imminent. brace yourselves.",
            "👀 lurking with intent to eavesdrop.",
            "🦗 dead silent but refuses to leave the vc.",
            "🧘‍♂️  spiritually AFK, physically present.",
            "🫧  background character energy rn.",
            "🔇  mic muted, presence loud.",
            "📺  vc on, watching netflix on the side. priorities.",
            "😶‍🌫️  vc therapy session arc loading...",
            "🥲  laughing at memes you’ll never see.",
            "🪩  talking to one person like it’s a full-blown TED Talk.",
            "💤  probably asleep. let them cook.",
        ]
        random_comment = random.choice(funny_comments)

        embed = discord.Embed(
            title=f"🔍 ♯ 𝘃𝗰 𝘀𝗻𝗼𝗼𝗽 𝗿𝗲𝗽𝗼𝗿𝘁 𝗳𝗼𝗿 {member.display_name} .ᐟ",
            color=discord.Color.from_str("#E75480")
        )
        embed.add_field(name="━━━━━━━━━━━━━━━━━━━━", value="‎", inline=False)  # Divider spacer
        embed.add_field(name="🎧 Currently Sabaw-ing in:", value=f"**{channel.name}**", inline=False)

        embed.add_field(name="🕒 Time Elapsed:", value=f"**{minutes}m {seconds}s**", inline=True)

        embed.add_field(name="💭 Status:", value=random_comment, inline=False)
        embed.set_footer(text="Keep slaying the vc life you little lore dropper 💅")

        await ctx.send(embed=embed)
    if user_id not in vc_sessions:
        await ctx.send(f"⚠️ {member.mention}'s vc time wasn't tracked properly... baka na-AFK?")

@announce.error
async def announce_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")
        
# --- Command: Check Rank ---
@bot.command(name="frag")
@commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
async def rank(ctx):
    user_id = str(ctx.author.id)
    guild_id = str(ctx.guild.id)

    no_xp_responses = [
        f"📉  {ctx.author.mention}, you have 0 XP. literal benchwarmer energy.",
        f"🫠  still XPless? ang tahimik mo naman, ghorl.",
        f"📵  wala kang ambag sa XP economy. get typing.",
        f"🥲  no level, no lore. start typing or stay irrelevant.",
        f"💤  no XP? baka ghost ka lang sa server.",
        f"🧂  XP? di uso sayo 'yan. timpla ka muna diyan.",
    ]

    if guild_id not in xp_data or user_id not in xp_data[guild_id]:
        await ctx.send(random.choice(no_xp_responses))
        return

    xp = xp_data[guild_id][user_id]["xp"]
    level = xp_data[guild_id][user_id]["level"]
    next_level_xp = level * 100

    sabaw_flavor = [
        "📉  XP mo parang love life ko — nonexistent.",
        "🧍  rank reveal? for what? para ma-humble ulit?",
        "🤖  kung XP lang ‘to, sana feelings din may tracking.",
        "🔮  you’re leveling up faster than my healing arc.",
        "🫠  frag ka nang frag, pero saan ka sa rankings? exactly.",
        "🎧  ganyan ka na lang? rank check tapos disappear?",
        "👁  your XP's cute... but where’s the impact?",
        "🥀  consistent sa pagiging inconsistent.",
        "📦  i packed your stats and left it at the door. get better soon.",
        "⚠️  side character energy. grind harder.",
        "💌  XP mo lang umakyat, hindi standards mo.",
        "🐸  you’re not even bronze-coded... more like rusted.",
        "🚬  smoking your stats for breakfast. try again.",
        "🛐  praying for your next level. and your aim.",
        "📺  caught you lurking and still not topfragging.",
        "🔇  stat ka nang stat pero wala ka namang ambag.",
        "🧃  juice cleanse? no. XP cleanse. start fresh pls.",
        "🏳️  wave the white flag — even your XP gave up.",
        "🧘‍♀️  sabaw is temporary, but your level is forever mid.",
        "🫵  this you? leveling slower than our trauma processing.",
    ]

    await ctx.send(
        f"📊  {ctx.author.mention}'s Rank:\n"
        f"Level: `{level}`\nXP: `{xp}/{next_level_xp}`\n"
        f"{random.choice(sabaw_flavor)}"
    )

@announce.error
async def announce_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")
        
# --- Command: Leaderboard ---
@bot.command(name="topfraggers")
@commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
async def leaderboard(ctx):
    guild_id = str(ctx.guild.id)

    if guild_id not in xp_data or not xp_data[guild_id]:
        await ctx.send("📉  walang leaderboard. puro lurker, zero grinder energy 😔")
        return

    # Sort users by XP
    rankings = sorted(xp_data[guild_id].items(), key=lambda x: x[1]["xp"], reverse=True)
    top = rankings[:10]

    # 🔮 Embed Setup
    embed = discord.Embed(
        title="🏆 ♯ 𝘁𝗼𝗽𝗳𝗿𝗮𝗴𝗴𝗲𝗿𝘀 𝗻𝗴 𝗺𝗴𝗮 𝗮𝘆𝗮𝘄 𝗽𝗮𝗮𝘄𝗮𝘁  .ᐟ",
        description="top fraggers, delulus, people with bottom tier life balance, and people who clearly need sleep.",
        color=discord.Color.from_str("#E75480")
    )

    embed.set_image(url="https://drive.google.com/uc?export=view&id=1GZTOQ5Qqo24mXt0SxatgHIz6SmJqSA2C")

    footer_lines = [
        "🧠  proof na hindi mo kailangan ng braincells to rank up.",
        "💅  top fraggers, emotionally unstable edition.",
        "📈  grinding XP kasi hindi nagrereply sa GC.",
        "🔫  this leaderboard is sponsored by caffeine and denial.",
        "🍜  sabaw supremacy since day one.",
        "🫠  hours played > hours slept.",
        "💔  peak performance with no sleep and too much trauma.",
        "🤸  XP farming habang may existential crisis.",
        "🎧  VC warriors, real life dodgers.",
        "🌙  gabi-gabi naglalaro, pero bakit ganon… lose streak pa rin.",
        "🎮  sila yung ‘one more game’ na 3AM na.",
        "💀  rank up? more like meltdown.",
        "🌪️  chaos agents in-game and in life.",
        "🫃  carried by trauma bonding and tactical delulu.",
        "😵‍💫  skill issue? no. life issue.",
        "🫵  ikaw na yung nasa leaderboard, ikaw pa ang lost.",
        "🔁  playing to escape, not to improve.",
        "📵  ignored DMs, but top 1 sa XP.",
        "🚨  therapy dropouts turned XP gods.",
        "🙃  they don’t sleep, they just disassociate.",
        "🤡  top frag, top sad.",
        "📉  high XP, low stability.",
        "🎤  mic muted, mental loud.",
        "👁️  seen-zoned everyone but not the grind.",
        "🛌  they log off valorant but never their emotional damage.",
        "🌸  fragged their way into the void.",
        "🪦  walang ambag sa GC pero top 3 sa leaderboard.",
        "🔥  carried the game, dropped the mental health.",
        "🧍  solo queue, solo life, solo tears.",
        "🥴  sabaw so strong, they transcended rank."
    ]
    embed.set_footer(text=random.choice(footer_lines))

    for i, (user_id, data) in enumerate(rankings[:10], start=1):
        member = ctx.guild.get_member(int(user_id))
        name = member.display_name if member else f"User Left ({user_id})"
        embed.add_field(
            name=f"{i}. {name}",
            value=f"Level: {data['level']} | XP: {data['xp']}",
            inline=False
        )

    await ctx.send(embed=embed)

@announce.error
async def announce_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")

@bot.command(name="helpme")
@commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
async def helpme(ctx):
    embed = discord.Embed(
        title=" :cosmos: ♯ 𝗰𝗼𝘀𝗺𝗼𝘀 𝗯𝗼𝘁 𝗰𝗼𝗺𝗺𝗮𝗻𝗱𝘀 .ᐟ",
        description="welcome to the soup! the commands below will help you swim, float, and maybe win a race or two.",
        color=discord.Color.from_str("##E75480")
    )

    embed.add_field(
        name="💬 ♯ 𝗴𝗲𝗻𝗲𝗿𝗮𝗹 𝗰𝗼𝗺𝗺𝗮𝗻𝗱𝘀 .ᐟ",
        value=(
            "`!say` — make me say something\n"
            "`!huy` — ping the bot in the most sabaw way\n"
            "`!boosters` — see server boosters appreciation board\n"
        ),
        inline=False
    )

    embed.add_field(
        name="📈 ♯ 𝘅𝗽 𝗮𝗻𝗱 𝗹𝗲𝘃𝗲𝗹𝘀 .ᐟ",
        value=(
            "`!frag` — check your xp and level\n"
            "`!topfraggers` — leaderboard of chaos (level & xp)\n"
            "`!vcstats` — see your current vc time & xp\n"
        ),
        inline=False
    )

    embed.add_field(
        name="🎯 ♯ 𝗶𝗻𝘁𝗲𝗿𝗮𝗰𝘁𝗶𝘃𝗲 𝗰𝗼𝗺𝗺𝗮𝗻𝗱𝘀 .ᐟ",
        value=(
            "`!roast` — delivers the perfect insult cocktail: 2 parts wit, 1 part chaos.\n"
            "`!sabaw` — for when your brain is soup and you need the words to prove it.\n"
            "`!who` — who to blame? randomly selects someone to take the fall. democracy, but chaotic.\n"
        ),
        inline=False
    )

    embed.set_footer(text="Pro tip: XP is earned by chatting, reacting, and VC-ing. Stay active, stay sabaw.")
    await ctx.send(embed=embed)
    
# --- Run Bot ---
keep_alive()

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("❌ DISCORD_TOKEN not found! Set it in the Replit Secrets tab (🔐 icon).")

bot.run(token)

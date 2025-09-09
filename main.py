import os
import random
import asyncio
import discord
from discord.ext import commands
from typing import cast, Optional
from discord import TextChannel
from keep_alive import keep_alive
        
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
    
# --- Bot Ready ---
@bot.event
async def on_ready():
    print(f"🚨 Bot is ready: {bot.user} | ID: {bot.user.id}")
    bot.add_view(VerifyButton())

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
        if not isinstance(channel, discord.TextChannel):
            print("❌ Boost channel not found or wrong type.")
            return
            
        booster_role = discord.utils.get(after.guild.roles, name=BOOST_ROLE_NAME)

        if booster_role:
            try:
                await after.add_roles(booster_role, reason="Server boosted ✨")
                print(f"✅ Booster role given to {after}")
            except discord.Forbidden:
                print(f"❌ Missing permissions to add {booster_role} to {after}")
            except discord.HTTPException as e:
                print(f"⚠️ Could not add role: {e}")

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
            
        try:
            await channel.send(embed=embed)
            print(f"📢 Boost notification sent in {channel}")
        except discord.Forbidden:
            print("❌ Bot cannot send messages in the boost channel.")
        except Exception as e:
            print(f"⚠️ Unexpected error sending boost embed: {e}")

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
@say_plain.error
async def say_plain_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")
        
# --- Boosters ---
@bot.command(name="boosters")
async def boosters(ctx):
    await ctx.message.delete()
    boosters = [member.mention for member in ctx.guild.members if member.premium_since]

    if boosters:
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
    
@test_bot.error
async def test_bot_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")
        
# --- Random Interactive Command ---
@bot.command(name="sabaw")
@commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
async def sabaw_line(ctx: commands.Context):
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

    # Avoid repeating the last line/intro if possible
    intro_choices = [x for x in intro_lines if x != last_sabaw_intro] or intro_lines
    line_choices = [x for x in sabaw_lines if x != last_sabaw_line] or sabaw_lines

    chosen_intro = random.choice(intro_choices)
    chosen_line = random.choice(line_choices)

    last_sabaw_intro = chosen_intro
    last_sabaw_line = chosen_line
        
    # dramatic sabaw bot loading
    thinking = await ctx.send("🤖 diagnosing emotional damage...")
    await asyncio.sleep(1.2)
    await thinking.edit(content="🩻 calculating iq deficit... please wait...")
    await asyncio.sleep(1.5)
    await thinking.edit(content=chosen_intro)
    await ctx.send(f"> {chosen_line}")

@sabaw_line.error
async def sabaw_line_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")
        
@bot.command(name="who")
@commands.cooldown(rate=1, per=30, type=commands.BucketType.user)
async def who(ctx):
    all_members = [m for m in ctx.guild.members if not m.bot]

    if not all_members:
        await ctx.send("⚠️ walang tao dito... server ghost town na 💀")
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

@who.error
async def who_error(ctx, error):
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

@roast.error
async def roast_error(ctx, error):
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
        name="🎯 ♯ 𝗶𝗻𝘁𝗲𝗿𝗮𝗰𝘁𝗶𝘃𝗲 𝗰𝗼𝗺𝗺𝗮𝗻𝗱𝘀 .ᐟ",
        value=(
            "`!roast` — delivers the perfect insult cocktail: 2 parts wit, 1 part chaos.\n"
            "`!sabaw` — for when your brain is soup and you need the words to prove it.\n"
            "`!who` — who to blame? randomly selects someone to take the fall. democracy, but chaotic.\n"
        ),
        inline=False
    )

    await ctx.send(embed=embed)

@helpme.error
async def helpme_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ {ctx.author.mention}, puro ping. kalma, ayaw? try again in `{error.retry_after:.1f}s`.")

# --- Run Bot ---
keep_alive()

token = os.getenv("DISCORD_TOKEN")
if not token:
    raise RuntimeError("❌ DISCORD_TOKEN not found! Set it in the Replit Secrets tab (🔐 icon).")

bot.run(token)

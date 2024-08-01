import discord
from discord.ext import commands
import asyncio
import re

# Intents
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.presences = True
intents.reactions = True

# Bot setup
bot = commands.Bot(command_prefix="!", intents=intents)

# Channel IDs
RED_CHANNEL_ID = 123456789098765432
BLUE_CHANNEL_ID = 123456789098765432
VOTING_CHANNEL_ID = 123456789098765432

# Available maps list with corresponding emojis
available_maps = {
    "Tohunga": "👍",
    "Overgrown": "👌",
    "Pipeline": "🙌",
    "Orbital": "🤟",
    "Kingdom": "🤙",
    "Derelict": "✋",
    "Turnpike": "👊",
    "Prague": "✌️",
    "Austria": "🙏"
}

# Variable to track if voting is in progress
voting_in_progress = False
voting_message = None
map_reactions = {map_name: 0 for map_name in available_maps.keys()}  # Track reactions for each map
users_votes_save = {}  # Track user votes
internal_participants = {}

# List of allowed commands for users and admins
allowed_commands = ["!internal", "!vote", "!close", "!r", "!b"]

# Role ID to exempt from message deletion
EXEMPT_ROLE_ID = 1234567890987654321

# Console log
@bot.event
async def on_ready():
    print(f'{bot.user} is online!')

# Command !internal
@bot.command(name="internal")
async def internal(ctx, *, time_input: str):
    print('Internal executed')
    global voting_in_progress

    # Define regular expression patterns
    time_pattern = r'^\d{1,2}:\d{2}$'
    cet_pattern = r'^\d{1,2}cet$'
    hour_pattern = r'^\d{1,2}$'

    # Check if arg matches HH:MM, HHcet, or HH pattern
    if re.match(time_pattern, time_input):
        hour = time_input
    elif re.match(cet_pattern, time_input):
        hour = time_input  # Leave HHcet format as it is
    elif re.match(hour_pattern, time_input):
        hour = f"{time_input}:00"  # Convert HH to HH:00 format
    else:
        await ctx.send("Invalid format! Please use **HH:MM**, **HHcet**, or **HH** format.")
        return

    message_content = "@everyone - `connect 85.27.184.76:27973; password OPT`"

    embed = discord.Embed(
        title="Internal Game",
        description=f"Can anyone play Internal today at {hour}?",
        color=0xFFFFFF
    )
    embed.set_footer(text="React below if you can play!")
    message = await ctx.send(content=message_content, embed=embed)
    await message.add_reaction("✅")

    # Set voting_in_progress to True when internal game starts
    voting_in_progress = True

@bot.event
async def on_reaction_add(reaction, user):
    if user == bot.user:
        return

    # Check if the reaction is to the message sent by the !internal
    if reaction.message.content.startswith("@everyone - `connect 85.27.184.76:27973; password OPT`"):
        # Check if the reaction is to the "✅"
        if reaction.emoji == "✅":
            # If yes, then bot send a notification
            channel = reaction.message.channel
            await channel.send(f"**{user.name}** signed to play Internal!")

@bot.event
async def on_reaction_remove(reaction, user):
    if user == bot.user:
        return

    # Check if the reaction is to the message sent by the !internal
    if reaction.message.content.startswith("@everyone - `connect 85.27.184.76:27973; password OPT`"):
        # Check if the reaction is to the "✅"
        if reaction.emoji == "✅":
            # If yes, then bot send a notification
            channel = reaction.message.channel
            await channel.send(f"**{user.name}** unsigned to play Internal.")

@internal.error
async def internal_error(ctx, error):
    if isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("You need to provide a time **`HH:MM`**, **`HHcet`**, or **`HH`** for the Internal game question!")

# Command !vote
@bot.command(name="vote")
async def vote(ctx):
    print('Vote executed')
    global voting_in_progress, voting_message, map_reactions, users_votes_save
    if not voting_in_progress:
        await ctx.send("Internal game not found, voting cannot be started.")
        return

    voting_channel = bot.get_channel(VOTING_CHANNEL_ID)
    if voting_channel:
        embed = discord.Embed(
            title="Vote for Map",
            description="React to this message to vote for the map you want to play",
            color=0xFFFFFF
        )

        for map_name, emoji in available_maps.items():
            embed.add_field(name=map_name.capitalize(), value=f"{emoji}", inline=False)

        voting_message = await voting_channel.send(embed=embed)
        map_reactions = {map_name: 0 for map_name in available_maps.keys()}  # Reset reaction counters
        users_votes_save = {}  # Reset user votes

        for emoji in available_maps.values():
            await voting_message.add_reaction(emoji)
    else:
        await ctx.send("Voting channel not found")

async def handle_reaction(payload, member):
    global map_reactions, voting_message, voting_in_progress, users_votes_save

    if voting_in_progress and voting_message and payload.message_id == voting_message.id:
        channel = bot.get_channel(payload.channel_id)
        if channel:
            try:
                message = await channel.fetch_message(payload.message_id)
                emoji = str(payload.emoji)

                if member.id in users_votes_save:
                    # Check if the user has already voted for two different maps
                    if len(users_votes_save[member.id]) >= 2:
                        await message.remove_reaction(emoji, member)
                        await channel.send(f"**{member.name}**, you can only vote for up to 2 maps!")
                        return

                    # Check if the user has already voted for this map
                    if emoji in users_votes_save[member.id]:
                        await message.remove_reaction(emoji, member)
                        await channel.send(f"**{member.name}**, you have already voted for this map!")
                        return

                    # Record the user's vote
                    users_votes_save[member.id].append(emoji)
                else:
                    # Initialize user's vote list
                    users_votes_save[member.id] = [emoji]

                # Check if the reaction is to one of the available maps
                for map_name, map_emoji in available_maps.items():
                    if emoji == map_emoji:
                        # Increase the response counter for the corresponding map
                        map_reactions[map_name] += 1

                        # Send a message indicating the current vote count for the map
                        await channel.send(f"**{member.name}** voted for {map_name}. Current votes for this map: {map_reactions[map_name]}")

                        # Check if any of the maps have reached 6 votes
                        if map_reactions[map_name] >= 6:
                            await close_voting(payload.channel_id, map_name, manual_close=False)
                        break
            except discord.NotFound:
                return

@bot.event
async def on_raw_reaction_add(payload):
    await asyncio.sleep(0.1)  # Small delay to ensure the events are not processed too quickly

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return

    member = guild.get_member(payload.user_id)
    if member is None or member.bot:
        return

    await handle_reaction(payload, member)

async def close_voting(channel_id, map_name, manual_close):
    global voting_in_progress, voting_message, map_reactions, users_votes_save

    if not voting_in_progress:
        return

    voting_channel = bot.get_channel(channel_id)
    if voting_channel and voting_message:
        await voting_message.delete()
        voting_in_progress = False
        voting_message = None
        users_votes_save = {}  # Clear user votes

        if manual_close:
            await voting_channel.send("Vote has been closed by an admin.")
        else:
            await voting_channel.send(f"Vote has been automatically closed as **{map_name}** reached 6 votes.")

        # Determine the map(s) with the most votes
        max_votes = max(map_reactions.values())
        most_voted_maps = [map_name for map_name, votes in map_reactions.items() if votes == max_votes]

        if max_votes >= 3:
            if len(most_voted_maps) == 1:
                await voting_channel.send(f"The map with the most votes is: **{most_voted_maps[0]}** with {max_votes} votes.")
            else:
                maps = ', '.join(most_voted_maps)
                await voting_channel.send(f"The maps with the most votes are: **{maps}** with {max_votes} votes each.")
        else:
            await voting_channel.send("Not enough votes to determine the winning map.")

        print("Voting closed.")
    else:
        print("Error: Voting channel or message not found while closing voting.")

# Command !close
@bot.command(name="close")
@commands.has_permissions(administrator=True)
async def close(ctx):
    print('Close executed')
    await close_voting(ctx.channel.id, "N/A", manual_close=True)

# Command !r
@bot.command(name="r")
@commands.has_permissions(administrator=True)
async def move_to_red(ctx, *, member_name: str):
    red_channel = bot.get_channel(RED_CHANNEL_ID)
    if red_channel:
        member = discord.utils.find(lambda m: member_name.lower() in m.name.lower(), ctx.guild.members)
        if member:
            try:
                await member.move_to(red_channel)
                await ctx.send(f"Moved **{member.name}** to Red T")
            except discord.DiscordException as e:
                await ctx.send(f"Failed to move {member.name}: {str(e)}")
        else:
            await ctx.send(f"No user found with name '{member_name}'.")
    else:
        await ctx.send("Red channel has not been found!")

@move_to_red.error
async def move_to_red_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have enough permissions to use this command")

# Command !b
@bot.command(name="b")
@commands.has_permissions(administrator=True)
async def move_to_blue(ctx, *, member_name: str):
    blue_channel = bot.get_channel(BLUE_CHANNEL_ID)
    if blue_channel:
        member = discord.utils.find(lambda m: member_name.lower() in m.name.lower(), ctx.guild.members)
        if member:
            try:
                await member.move_to(blue_channel)
                await ctx.send(f"Moved **{member.name}** to Blue T")
            except discord.DiscordException as e:
                await ctx.send(f"Failed to move {member.name}: {str(e)}")
        else:
            await ctx.send(f"No user found with name '{member_name}'.")
    else:
        await ctx.send("Blue channel has not been found!")

@move_to_blue.error
async def move_to_blue_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have enough permissions to use this command")

@bot.event
async def on_message(message):
    if not message.author.bot:
        if message.channel.id == VOTING_CHANNEL_ID:
            if EXEMPT_ROLE_ID not in [role.id for role in message.author.roles]:
                if message.content.split()[0] not in allowed_commands:
                    await message.delete()
                    await message.channel.send(f"{message.author.mention}, please use <#950137109644197890> for chatting. Here, use **`!internal`** or **`!vote`** cmds.")
                    print(f"Message deleted from {message.author.name}. Content: {message_content}")
        elif "!internal" in message.content.lower():
            global voting_in_progress
            voting_in_progress = True

    await bot.process_commands(message)

bot.run('yourtoken')

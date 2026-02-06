import os
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
Token = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="s!", intents=intents)
tree = bot.tree

# Connect to a database file
import psycopg2
import os

DATABASE_URL = os.getenv("DATABASE_URL")
from psycopg2.pool import SimpleConnectionPool

db_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,  # good for your size
    dsn=DATABASE_URL,
    sslmode="require"
)

def get_db():
    conn = db_pool.getconn()
    return conn, conn.cursor()

def fetch_one(query, params):
    conn, c = get_db()
    try:
        c.execute(query, params)
        return c.fetchone()
    finally:
        db_pool.putconn(conn)

conn, c = get_db()

try:
    c.execute("""
    CREATE TABLE IF NOT EXISTS roles (
        user_id BIGINT PRIMARY KEY,
        guild_id BIGINT NOT NULL,
        role_id BIGINT NOT NULL,
        role_name TEXT NOT NULL
    )
    """)
    conn.commit()
finally:
    db_pool.putconn(conn)

### DEV OVERRIDE
TESTER_ID = 393891661349912586

GUILD_IDS = [1436430586226016453, 1348602178696380487, 1465559314587582647]

@tree.command(name="hello", description="Say hello to Semiu!")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f'Hello {interaction.user.display_name}! 👋')

@tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(
    description=
    "> * Use `/help` to show all available commands\n"
    "> * Use `/hello` to say hi to Semiu\n"
    "> * Use `/role claim <name>` to claim a custom role\n"
    "> * Use `/role name <name>` to change the role name\n"
    "> * Use `/role color <hex color>` to change the role color\n"
    "> * Use `/role gradient <hex color> <hex color>` to change the role color to a gradient\n"
    "> * Use `/role delete` to delete your custom role\n"
    "> * Use `/role icon <image>` to change the role icon",
    colour=0xca7648
    )
    embed.set_author(name="Here is the commands list", icon_url=interaction.user.display_avatar.url)
    embed.set_footer(text="/help for commands list")
    
    await interaction.followup.send(embed=embed, ephemeral=False)

#########################
##### ROLE COMMANDS #####
#########################

role_group = app_commands.Group(
    name="role",
    description="Manage your custom role"
)

@role_group.command(name="claim", description="Claim your own custom role")
async def claim(interaction: discord.Interaction, role_name: str = None):
        await interaction.response.defer(ephemeral=False)

        guild = interaction.guild
        member = interaction.user

        ### CHECK IF MEMBER IS A SERVER BOOSTER
        if not member.premium_since and member.id != TESTER_ID:
            embed = discord.Embed(
                description="❌ You need to be a **Server Booster** to claim a custom role!",
                colour=0xff0000
            )
            embed.set_author(name="Server boost Required")
            embed.set_footer(text="Boost the server to claim your custom role")
            await interaction.followup.send(embed=embed, ephemeral=False)
            return

        if role_name is None:
            role_name = f"{member.display_name}'s Role"

        conn, c = get_db()
        try:
            c.execute("SELECT role_id FROM roles WHERE user_id = %s", (member.id,))
            result = c.fetchone()
        finally:
            db_pool.putconn(conn)


        ### Check database for existing role
        if result:
            existing_role = guild.get_role(result[0])
            if existing_role:
                embed = discord.Embed(
                    #title=" Custom role already claimed!",
                    description=f"❌ You already have a custom role: @{existing_role.name}\n"
                    "> * Use `/role name <name>` to change the role name\n"
                    "> * Use `/role color <hex color>` to change the role color\n"
                    "> * Use `/role gradient <hex color> <hex color>` to change the role color to a gradient\n"
                    "> * Use `/role delete` to delete your custom role\n"
                    "> * Use `/role icon <image>` to change the role icon",
                    colour=0xff0000
                )
                embed.set_author(name="ERROR: Custom role already claimed!")
                embed.set_footer(text="/help for commands list")
        
                await interaction.followup.send(embed=embed, ephemeral=False)
                return
            else:
                # User does not have role, delete from database
                conn, c = get_db()
                try:
                    c.execute("DELETE FROM roles WHERE user_id = %s", (member.id,))
                    conn.commit()
                finally:
                    db_pool.putconn(conn)


        ### Create role
        # 1. Create the new role (always starts at bottom)
        new_role = await guild.create_role(
            name=role_name,
            colour=discord.Color.random(),
            hoist=False,
            mentionable=False
        )

        # 2. Fetch roles again to ensure cache is correct
        await guild.fetch_roles()
        new_role = guild.get_role(new_role.id)

        ### WILL LOOK FOR A ROLE CALLED "SERVER BOOSTER". WILL NOT WORK WITH OTHER ROLE NAMES. KEEP IN MIND.
        booster_role = discord.utils.find(
            lambda r: "server booster" in r.name.lower(),
            guild.roles
        )

        if booster_role:
            try:
                await guild.fetch_roles()
                target_position = min(booster_role.position+1, guild.me.top_role.position-1)
                await new_role.edit(position=target_position)
            except discord.Forbidden:
                print("`ERROR: NO PERMISSION TO MOVE ROLE. GRANT RELEVANT PERMISSIONS.`")
        else:
            print('`NO SERVER BOOSTER ROLE FOUND. SERVER BOOSTER ROLE REQUIRED. OTHERWISE TRY RENAMING THE SERVER BOOSTER ROLE `"Server Booster"')

        ### Give role to member
        await member.add_roles(new_role)

        ### Store role in database

        conn, c = get_db()
        try:
            c.execute(
                "INSERT INTO roles (user_id, guild_id, role_id, role_name) VALUES (%s, %s, %s, %s)",
                (member.id, guild.id, new_role.id, new_role.name)
            )
            conn.commit()
        finally:
            db_pool.putconn(conn)


        ### Claim message
        embed = discord.Embed(
            #title="Custom role claimed!",
            description=f"Thank you for boosting **{guild.name}**, {interaction.user.display_name}!\n"
            "Here is your own custom role! 🎉\n"
            "> * Use `/role name <name>` to change the role name\n"
            "> * Use `/role color <hex color>` to change the role color\n"
            "> * Use `/role gradient <hex color> <hex color>` to change the role color to a gradient\n"
            "> * Use `/role delete` to delete your custom role\n"
            "> * Use `/role icon <image>` to change the role icon",
            colour=0xca7648
        )
        embed.set_author(name=f"{interaction.user.display_name} has claimed a custom role!", icon_url=interaction.user.display_avatar.url)
        embed.set_footer(text="/help for commands list")
        
        await interaction.followup.send(embed=embed, ephemeral=False)

@role_group.command(name="delete", description="Delete your custom role")
async def delete(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        
        guild = interaction.guild
        member = interaction.user

        ### Look up the role in database
        conn, c = get_db()
        try:
            c.execute("SELECT role_id FROM roles WHERE user_id = %s", (member.id,))
            result = c.fetchone()
        finally:
            db_pool.putconn(conn)


        ### No custom role detected
        if not result:
                embed = discord.Embed(
                description="❌ No custom role was detected\n"
                    "> * Use `/role claim <name>` to claim a custom role!",
                    colour=0xff0000
                )
                embed.set_author(name="ERROR: No custom role detected!")
                embed.set_footer(text="/help for commands list")
                await interaction.followup.send(embed=embed, ephemeral=False)
                return
        
        ### role exists
        role_id = result[0]
        role = guild.get_role(role_id)

        if role:
            try:
                await member.remove_roles(role)
                await role.delete()
                embed = discord.Embed(
                    description=f'Your custom role "{role.name}", has been successfully deleted!\n'
                    "> * Use `/role claim <name>` to claim a new custom role",
                    colour=0x00ff00
                )
                embed.set_author(name="Role successfully deleted!", icon_url=interaction.user.display_avatar.url)
                embed.set_footer(text="/help for commands list")
                conn, c = get_db()
                try:
                    c.execute("DELETE FROM roles WHERE user_id = %s", (member.id,))
                    conn.commit()
                finally:
                    db_pool.putconn(conn)

        
                await interaction.followup.send(embed=embed, ephemeral=False)
            except discord.Forbidden:
                embed = discord.Embed(
                    description="❌ I do not have permission to edit your role!\n"
                    "Please ask a moderator give me the correct permission/",
                    colour=0xff0000
                )
                embed.set_author(name="Error: Permission denied!")
                embed.set_footer(text="/help for commands list")
        
                await interaction.followup.send(embed=embed, ephemeral=False)
            except discord.HTTPException:
                embed = discord.Embed(
                    description="❌ Your role could not be deleted, please try again later",
                    colour=0xff0000
                )
                embed.set_author(name="Error: HTTP ERROR")
                embed.set_footer(text="/help for commands list")
        
                await interaction.followup.send(embed=embed, ephemeral=False)
        
        else:
            embed = discord.Embed(
                    description="❌ Your role was already deleted manually\n"
                    "> * Use `/role claim <name>` to claim a new custom role",
                    colour=0xff0000
                )
            embed.set_author(name="Role was already deleted!", icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text="/help for commands list")
        
            await interaction.followup.send(embed=embed, ephemeral=False)
            conn, c = get_db()
            try:
                c.execute("DELETE FROM roles WHERE user_id = %s", (member.id,))
                conn.commit()
            finally:
                db_pool.putconn(conn)


@role_group.command(name="name", description="Change the name of your custom role")
async def name(interaction: discord.Interaction, new_name: str = None):
        await interaction.response.defer(ephemeral=False)
        
        member = interaction.user
        guild = interaction.guild
        
        ### Look up the role in database
        conn, c = get_db()
        try:
            c.execute("SELECT role_id FROM roles WHERE user_id = %s", (member.id,))
            result = c.fetchone()
        finally:
            db_pool.putconn(conn)


        ### No custom role detected
        if not result:
                embed = discord.Embed(
                description="❌ No custom role was detected\n"
                    "> * Use `/role claim <name>` to claim a custom role!",
                    colour=0xff0000
                )
                embed.set_author(name="ERROR: No custom role detected!")
                embed.set_footer(text="/help for commands list")
                await interaction.followup.send(embed=embed, ephemeral=False)
                return
        
        role = guild.get_role(result[0])
        if not role:
            ### Role was deleted manually, clean database
            conn, c = get_db()
            try:
                c.execute("DELETE FROM roles WHERE user_id = %s", (member.id,))
                conn.commit()
            finally:
                db_pool.putconn(conn)

            embed = discord.Embed(
                description="❌ Your custom role no longer exists.\n> * Use `/role claim <name>` to claim a new one.",
                colour=0xff0000
            )
            embed.set_author(name="ERROR: Role not found!")
            embed.set_footer(text="/help for commands list")
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        ### change role name
        try:
            await role.edit(name=new_name)
            conn, c = get_db()
            try:
                c.execute(
        "UPDATE roles SET role_name = %s WHERE user_id = %s",
                    (new_name, member.id)
                )
                conn.commit()
            finally:
                db_pool.putconn(conn)

            embed = discord.Embed(
                description=f"✅ Your role name has been updated to **{new_name}**!",
                colour=0xca7648
            )
            embed.set_author(name="Role name updated!", icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text="/help for commands list")
            await interaction.followup.send(embed=embed, ephemeral=False)
            
        except discord.Forbidden:
            embed = discord.Embed(
                description="❌ I do not have permission to edit your role!\n"
                "Please ask a moderator give me the correct permission/",
                colour=0xff0000
            )
            embed.set_author(name="ERROR: Permission denied!")
            embed.set_footer(text="/help for commands list")
            await interaction.followup.send(embed=embed, ephemeral=False)

@role_group.command(name="color", description="Change the color of your custom role to a flat color")
async def color(interaction: discord.Interaction, hex_color: str):
        await interaction.response.defer(ephemeral=False)
        
        member = interaction.user
        guild = interaction.guild

        ### Look up the role in database
        conn, c = get_db()
        try:
            c.execute("SELECT role_id FROM roles WHERE user_id = %s", (member.id,))
            result = c.fetchone()
        finally:
            db_pool.putconn(conn)


        ### No custom role detected
        if not result:
                embed = discord.Embed(
                description="❌ No custom role was detected\n"
                    "> * Use `/role claim <name>` to claim a custom role!",
                    colour=0xff0000
                )
                embed.set_author(name="ERROR: No custom role detected!")
                embed.set_footer(text="/help for commands list")
                await interaction.followup.send(embed=embed, ephemeral=False)
                return
        
        role = guild.get_role(result[0])
        if not role:
            ### Role was deleted manually, clean database
            conn, c = get_db()
            try:
                c.execute("DELETE FROM roles WHERE user_id = %s", (member.id,))
                conn.commit()
            finally:
                db_pool.putconn(conn)

            embed = discord.Embed(
                description="❌ Your custom role no longer exists.\n> * Use `/role claim <name>` to claim a new one.",
                colour=0xff0000
            )
            embed.set_author(name="ERROR: Role not found!")
            embed.set_footer(text="/help for commands list")
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
    ### Convert the hex string into a discord.Color
        try:
            if hex_color.startswith("#"):
                hex_color = hex_color[1:]
            color_value = discord.Color(int(hex_color, 16))
        except ValueError:
            embed = discord.Embed(
                description='❌ Invalid color format! Use the hexadecimal color format.\nIt should look something like "#FF5733".',
                colour=0xff0000
            )
            embed.set_author(name="ERROR: Invalid color format!")
            embed.set_footer(text="/help for commands list")
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        ### Change role color
        try:
            await role.edit(colour=color_value)
            embed = discord.Embed(
                description=f"✅ Your role color has been updated to **#{hex_color.upper()}**!",
                colour=color_value
            )
            embed.set_author(name="Role color updated!", icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text="/help for commands list")
            await interaction.followup.send(embed=embed, ephemeral=False)

        except discord.Forbidden:
            embed = discord.Embed(
                description="I do not have permission to edit your role!\n"
                "Please ask a moderator give me the correct permission/",
                colour=0xff0000
            )
            embed.set_author(name="ERROR: Permission denied!")
            embed.set_footer(text="/help for commands list")
            await interaction.followup.send(embed=embed, ephemeral=False)

@role_group.command(name="icon", description="Change the icon of your custom role")
async def icon(interaction: discord.Interaction, image: discord.Attachment = None):
        await interaction.response.defer(ephemeral=False)
        
        member = interaction.user
        guild = interaction.guild
        
        ### Check if server is boosted enough
        if guild.premium_tier < 2:
            embed = discord.Embed(
                description="❌ This server must be **boost level 2 or higher** to use role icons.",
                colour=0xff0000
            )
            embed.set_author(name="Cannot set role icon")
            embed.set_footer(text="/help for commands list")
            await interaction.followup.send(embed=embed, ephemeral=False)
            return

        ### Look up the role in database
        conn, c = get_db()
        try:
            c.execute("SELECT role_id FROM roles WHERE user_id = %s", (member.id,))
            result = c.fetchone()
        finally:
            db_pool.putconn(conn)


        ### No custom role detected
        if not result:
                embed = discord.Embed(
                description="❌ No custom role was detected\n"
                    "> * Use `/role claim <name>` to claim a custom role!",
                    colour=0xff0000
                )
                embed.set_author(name="ERROR: No custom role detected!")
                embed.set_footer(text="/help for commands list")
                await interaction.followup.send(embed=embed, ephemeral=False)
                return
        
        role = guild.get_role(result[0])
        if not role:
            ### Role was deleted manually, clean database
            conn, c = get_db()
            try:
                c.execute("DELETE FROM roles WHERE user_id = %s", (member.id,))
                conn.commit()
            finally:
                db_pool.putconn(conn)

            embed = discord.Embed(
                description="❌ Your custom role no longer exists.\n> * Use `/role claim <name>` to claim a new one.",
                colour=0xff0000
            )
            embed.set_author(name="ERROR: Role not found!")
            embed.set_footer(text="/help for commands list")
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        ### CHECK IF THERE IS IMAGE
        if not image:
            embed = discord.Embed(
                description="❌ Please provide an image URL or attachment to set as your role icon.",
                colour=0xff0000
            )
            embed.set_author(name="No image provided")
            embed.set_footer(text="/help for commands list")
            await interaction.followup.send(embed=embed, ephemeral=False)
            return
        
        ### SET IMAGE
        try:
            image_bytes = await image.read()
            await role.edit(display_icon=image_bytes)
            embed = discord.Embed(
                description=f"✅ Your role icon has been updated!",    
                colour=0x00ff00
            )
            embed.set_author(name="Role icon updated", icon_url=interaction.user.display_avatar.url)
            embed.set_footer(text="/help for commands list")
            await interaction.followup.send(embed=embed, ephemeral=False)

        except discord.Forbidden:
            embed = discord.Embed(
                    description="❌ I do not have permission to edit your role!\n"
                    "Please ask a moderator give me the correct permission/",
                    colour=0xff0000
                )
            embed.set_author(name="Error: Permission denied!")
            embed.set_footer(text="/help for commands list")

            await interaction.followup.send(embed=embed, ephemeral=False)
        
        except discord.HTTPException:
                embed = discord.Embed(
                    description="❌ Your role could not be updated. Please make sure the image is valid and try again",
                    colour=0xff0000
                )
                embed.set_author(name="Error: HTTP ERROR")
                embed.set_footer(text="/help for commands list")
        
                await interaction.followup.send(embed=embed, ephemeral=False)

@role_group.command(name="gradient", description="Change the color of your custom role to a gradient")
async def gradient(interaction: discord.Interaction, color1: str = None, color2: str = None):
        await interaction.response.defer(ephemeral=False)

        embed = discord.Embed(
            description="❌ Discord's API does not allow for developers to utilize gradient role colors yet.\n"
                        "Sorry for the inconvenience!",
            colour=0xff0000
        )
        embed.set_author(name="Gradient roles unavailable")
        embed.set_footer(text="/help for commands list")

        await interaction.followup.send(embed=embed, ephemeral=False)

        # member = interaction.user
        # guild = interaction.guild
        
        # ### Check if server is boosted enough
        # if guild.premium_tier < 2:
        #     embed = discord.Embed(
        #         description="❌ This server must be **boost level 3 ** to use role gradients.",
        #         colour=0xff0000
        #     )
        #     embed.set_author(name="Cannot set role icon")
        #     embed.set_footer(text="/help for commands list")
            
        #     await interaction.followup.send(embed=embed, ephemeral=False)
        #     return

        # ### Look up the role in database
        # conn, c = get_db()
        # try:
        #     c.execute("SELECT role_id FROM roles WHERE user_id = %s", (member.id,))
        #     result = c.fetchone()
        # finally:
        #    db_pool.putconn(conn)


        # ### No custom role detected
        # if not result:
        #         embed = discord.Embed(
        #         description="❌ No custom role was detected\n"
        #             "> * Use `/role claim <name>` to claim a custom role!",
        #             colour=0xff0000
        #         )
        #         embed.set_author(name="ERROR: No custom role detected!")
        #         embed.set_footer(text="/help for commands list")
                
        #         await interaction.followup.send(embed=embed, ephemeral=False)
        #         return
        
        # role = guild.get_role(result[0])
        # if not role:
        #     ### Role was deleted manually, clean database
        #     conn, c = get_db()
        #     try:
        #         c.execute("DELETE FROM roles WHERE user_id = %s", (member.id,))
        #         conn.commit()
        #     finally:
        #         db_pool.putconn(conn)

        #     embed = discord.Embed(
        #         description="❌ Your custom role no longer exists.\n> * Use `/role claim <name>` to claim a new one.",
        #         colour=0xff0000
        #     )
        #     embed.set_author(name="ERROR: Role not found!")
        #     embed.set_footer(text="/help for commands list")
            
        #     await interaction.followup.send(embed=embed, ephemeral=False)
        #     return
        
        # ### Convert hex strings to integers
        # try:
        #     if color1.startswith("#"): color1 = color1[1:]
        #     if color2.startswith("#"): color2 = color2[1:]
        #     gradient_color = discord.Color.from_gradient(int(color1, 16), int(color2, 16))
        # except ValueError:
        #     embed = discord.Embed(
        #         description='❌ Invalid color format! Use the hexadecimal color format.\nIt should look something like "#FF5733".',
        #         colour=0xff0000
        #     )
        #     embed.set_author(name="ERROR: Invalid color format!")
        #     embed.set_footer(text="/help for commands list")
            
        #     await interaction.followup.send(embed=embed, ephemeral=False)
        #     return

        # ### change role color to a gradient using the two hexadecimal values that the user has entered
        # try:
        #     await role.edit(colour=gradient_color)
        #     embed = discord.Embed(
        #         description=f"✅ Your role gradient has been updated from **#{color1.upper()}** to **#{color2.upper()}**!",
        #         colour=gradient_color
        #     )
        #     embed.set_author(name="Role gradient updated!", icon_url=interaction.user.display_avatar.url)
        #     embed.set_footer(text="/help for commands list")
            
        #     await interaction.followup.send(embed=embed, ephemeral=False)

        # except discord.Forbidden:
        #     embed = discord.Embed(
        #         description="❌ I do not have permission to edit your role!\n"
        #             "Please ask a moderator give me the correct permission/",
        #             colour=0xff0000
        #         )
        #     embed.set_author(name="Error: Permission denied!")
        #     embed.set_footer(text="/help for commands list")
            
        #     await interaction.followup.send(embed=embed, ephemeral=False)

tree.add_command(role_group)

@bot.event
async def on_ready():
    try:
        print("\nRegistered app commands:")
        for cmd in tree.get_commands():
            print(f"- {cmd.name} ({type(cmd)})")

        for guild_id in GUILD_IDS:
            guild = discord.Object(id=guild_id)
            await tree.sync(guild=guild)
            print(f"Slash commands synced instantly to guilds {guild_id}")
        
        await tree.sync()
        print(f"Slash commands synced globally ({len(tree.get_commands())} total)\n")

    except Exception as e:
        print(f"Error syncing commands: {e}")

    print("\n[ SEMIU IS ONLINE ]\n")

@bot.event
async def on_guild_join(guild):
    print(f"Joined server {guild.name}")
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            await channel.send("Semiu on duty 👓🫡")
            break

bot.run(Token)
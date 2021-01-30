A personal Discord Bot written with discord.py for the game ffxiv

Bot Invite link [here](https://discordapp.com/oauth2/authorize?client_id=732960151434297394&scope=bot&permissions=18496)

Commands List
-------------
**Info:** Bot prefix is `tataru`, < > refers to a required argument, [ ] is optional,do not actually type these. <br>
"--" denotes a flag for an argument eg. --flagname argument

### Help ###
Command and Aliases | Description | Usage
---------------|--------------|-------
`help` | Shows help about a command, or category | `tataru help <command name>`, `tataru help <category name>`

### No Category ###
Command and Aliases | Description | Usage
---------------|--------------|-------
`ping` | Check the bot's websocket latency | `tataru ping`
`prefix` | Returns the bot current prefixes | `tataru prefix`
`say` | Echo a message | `tataru say <sup, biches>`
`about` | Get info about the bot | `tataru about`
`source` | Returns the bot's github url | tataru source [command]

### Mirapi ###

Command and Aliases | Description | Usage
----------------|--------------|-------
`mirapi, mi` | The main command for mirapi by itself returns glamours on the main page | `tataru mirapi`
`acceptable_flags, af` | Returns acceptable arguments that can be passed as flags for equipment and filters commands | `tataru acceptable_flags`
`getjobids, gji` | Returns acceptable job ids for the --j flag | `tataru getjobids`
`getraceids, gri` | Returns acceptable race ids for the --r flag | `tataru getraceids`

### mirapi (command) ###
Sub Command and Aliases | Description | Usage
----------------|--------------|-------
`filters, f, filter` | Returns glamours based on flags (--r, --g, --j) | `tataru mirapi filters --r <4> --g <f> --j <war>`, `tataru mirapi filters --r <lalafell>`
`search, s, se` |The main command for retrieving glamours on mirapi based on a keyword | `tataru mirapi search <keyword>`

### search (command) ###
Sub Command and Aliases | Description | Usage
----------------|--------------|-------
`filters, f, filter` | Returns glamours based on a keyword with optional flags (--r, --g, --j) | `tataru mirapi search filters <詩人らしく> --r <4> --g <f> --j <war>`, `tataru mirapi search filters --r <lalafell>`
`equipment, eq` | Returns glamours based on equipment name with optional flags (--r, --g, --j) | `tataru mirapi search equipment <no.2 type b boots> --r <4> --g <f> --j <war>`, `tataru mirapi search equipment <cotton kurta> --r <lalafell>`

### LodeStone ###

Command and Aliases | Description | Usage
----------------|--------------|-------
`iam` | Save a character | `tataru iam <world> <forename> <surname>`
`portrait, por` | Returns a character's lodestone portrait | `tataru portrait <world> <forename> <surname>`, `tataru portrait`, `tataru portrait <@user>`

### GamerScape ###

Command and Aliases | Description | Usage
----------------|--------------|-------
`gamerscape_image_find, gif` | Search for an image on gamerscape by filename  | `tataru gif <name>`
`gamerscape_image_search, gis` | Retrieves image names on gamerscape by filename (case sensitive) | `tataru gis <name>`
`gamerscape_search, gs` | Retrieves pages on gamerscape based on the query | `tataru gs <query>`

### gamerscape_image_search (command) ###
Sub Command and Aliases | Description | Usage
----------------|--------------|-------
`gamerscape_search, gs` | Retrieves images for glamour on gamerscape by filename with optional flags (--g, --r)| `tataru gis glam <no.2 type b boots>, tataru gis glam <no.2 type b boots> --r <lalafell> -g <female>`


### FFlogs ###

Command and Aliases | Description | Usage
----------------|--------------|-------
`encounterlogs, el, encounter` | returns all parses/logs for an encounter by name as found on fflogs | `tataru el <shadowkeeper> <world> <forename> <surname>`, `tataru el <e10n> <@User>`, `tataru el <"cloud of darkness">`
`search` | search for a player or free company and retrieve their fflogs page | `tataru search <Calad Baal>`
`tierlogs, tl` | Displays raid parses for the current expansion's raid tier | `tataru tierlogs`, `tataru tierlogs <@User>`, `tataru tierlogs <world> <forename> <surname>`

### tierlogs (command) ###
Sub Command and Aliases | Description | Usage
----------------|--------------|-------
`best, b` | Displays best raid parses for the current expansion's content | `tataru tierlogs best`, `tataru tierlogs best <@User>`, `tataru tierlogs best <world> <forename> <surname>`

### best (command) ###
Sub Command and Aliases | Description | Usage
----------------|--------------|-------
`adps` | sets the metric for rankings to adps | `tataru tierlogs best adps`, `tataru tierlogs best adps <@User>`, `tataru tierlogs best adps <world> <forename> <surname>`


## Running/Self Hosting<br>
1. Requires python 3.6 or higher
   <br><br>
2. you will need to obtain api keys from https://www.fflogs.com/ and https://xivapi.com/ 
   <br><br>
3. Install dependencies 
   <br>pip install -r requirements.txt
   <br><br>
4. Create the database
   <br>You will need to create a postgres database owned by postgres and require PostgreSQL 9.5 or higher.
   <br>The bot will add the tables on startup.
   <br><br>
5. Setting up configuration
   example configuration can be found in the exampleconfig.py,<br>create a config.py similar to this 
   and place it in the config directory
   <br><br>
6. Upon starting the bot by running the main.py file you will finally need to run the add_zones command to 
   setup the fflogs cog

## Requirements<br>
* Python 3.6+
* v1.3.4+ of discord.py
* FFlogs account
* lru-dict
* Asyncpg
* Beautifulsoup4
* Jishaku
* Typing
* Psutil
* pyxivapi
* discord-ext-menus
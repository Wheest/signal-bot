#!/usr/bin/env python3
import os
import re
import json
import pickle
import tempfile
import requests
import time
import anyio
from collections import defaultdict

from openai import OpenAI

from semaphore import Bot, ChatContext, Attachment

from utils import save_image, SunoAPI, AwsEc2Api

client = OpenAI()


class MyBot:
    def __init__(
        self,
        bot_number: str,
        bot_default_name: str,
        bot_default_model: str,
        admin_number: str,
        admin_uuid: str,
        socket_path: os.PathLike,
        usernames_file: os.PathLike,
        allow_list_file: os.PathLike,
    ):
        self.bot_number = bot_number
        self.bot_default_name = bot_default_name
        self.bot_default_model = bot_default_model
        self.admin_number = admin_number
        self.admin_uuid = admin_uuid
        self.socket_path = socket_path
        self.allow_list_file = allow_list_file
        self.MAX_TOKEN = 256
        self.MAX_MESSAGES = 50
        self.shared_tmpfs = "/shared_tmpfs/"
        # self.load_state()
        self.load_allow_list()
        self.usernames_file = usernames_file
        self.usernames = self.load_usernames()

        # Mapping of command substrings to member function calls.
        #
        # Only one special command can be executed at a time, and
        # the special commands take precedence over the regular commands.
        # In addition, if there are multiple special commands in a message,
        # the first one in this dictionary will be executed.
        self.special_commands = {
            "/help": (self.help_fn, "Get help on how to use the bot"),
            "/set-name": (self.set_name, "Set the name the bot uses for you"),
            "/server-on": (self.server_on, "Turn on the Minecraft server"),
            "/server-off": (self.server_off, "Turn off the Minecraft server"),
            "/clear": (self.clear_fn, "Clear the chat history"),
            "/suno-limits": (self.suno_limits_fn, "Returns the limits of Suno API"),
            "/echo": (self.echo_fn, "Echo the message back"),
        }

        # Mapping of command substrings to member function calls.
        self.commands = {
            "/thots": (self.convo_fn, "Get an LLM to respond to a message"),
            "/dalle3": (self.dalle3_fn, "DALLE-3 model"),
            "/suno": (self.suno_fn, "Suno music generation model"),
            "/suno-custom": (self.suno_custom_fn, "Suno music generation model"),
            # ... add all other command mappings
        }
        self.admin_commands = {
            "/awright": (self.admin_fn, "Admin command for initial test"),
        }

    def load_usernames(self):
        # Load the usernames from a JSON file
        # unknown users are assigned the default name "User"
        try:
            with open(self.usernames_file) as f:
                usernames = json.load(f)
            return defaultdict(lambda: "User", usernames)
        except FileNotFoundError:
            print("No usernames file found")
            return defaultdict(lambda: "User")

    def save_usernames(self):
        # Save the usernames as JSON
        with open(self.usernames_file, "w") as f:
            json.dump(self.usernames, f, indent=2)

    async def get_username(self, ctx):
        # Get the username for a given number
        number = ctx.message.source.number
        if number is None:
            # use UUID as the key
            username = self.usernames.get(ctx.message.source.uuid)
        else:
            username = self.usernames.get(number)
            self.usernames[ctx.message.source.uuid] = username
            self.save_usernames()

        if username == "User" or username is None:
            self.usernames[ctx.message.source.uuid] = "User"
            self.save_usernames()
            print("going to send a message")
            # send a message to the user to set their name
            await self.system_message(ctx, "Please set your name using /set-name")
        return username

    def load_allow_list(self):
        # read the allow list from a JSON file. they keys are the valid chats
        try:
            with open(self.allow_list_file) as f:
                self.allow_list = json.load(f)
        except FileNotFoundError:
            print("No allow list file found")
            self.allow_list = {}

    async def system_message(self, ctx, msg):
        await ctx.message.reply(f"[PG-Tips: {msg}]", quote=True)

    async def clear_fn(self, ctx):
        group_id = ctx.message.get_group_id()
        with open(f"/app/state/{group_id}.pkl", "wb") as f:
            pickle.dump([], f)
        await self.system_message(ctx, "Chat history cleared")

    async def echo_fn(self, ctx):
        msg = ctx.message.get_body()
        msg = self.remove_commands(msg)
        await ctx.message.reply("(echo): " + msg.strip())

    def save_state(self, ctx, msg_history, msg, number_override=None):
        # add the message to the state (a series of messages)
        # shoild be fast to load and store
        # stored under state/group_id.pkl
        if number_override:
            number = number_override
        else:
            if ctx.message.source.number is None:
                number = ctx.message.source.uuid
            else:
                number = ctx.message.source.number
        msg_history.append((number, msg))  # tuple of (number, message)
        group_id = ctx.message.get_group_id()
        # if the file does not exist, it will be created
        os.makedirs(os.path.dirname("/app/state/"), exist_ok=True)
        group_id = group_id.replace("/", "_")
        # only store the last MAX_MESSAGES
        msg_history = msg_history[-self.MAX_MESSAGES :]
        with open(f"/app/state/{group_id}.pkl", "wb") as f:
            pickle.dump(msg_history, f)

    def load_state(self, group_id):
        # Load the state using pickle
        # if the file does not exist, return an empty dict
        group_id = group_id.replace("/", "_")
        try:
            with open(f"/app/state/{group_id}.pkl", "rb") as f:
                return pickle.load(f)
        except FileNotFoundError:
            return []

    async def process_commands(self, msg, ctx):
        words = msg.lower().split()

        for command in self.special_commands:
            # only allow one special command at a time
            if command in words:
                await self.special_commands[command][0](ctx)
                print(f"Special command: {command}")
                return

        number = ctx.message.source.number
        uuid = ctx.message.source.uuid
        if number == self.admin_number or uuid == self.admin_uuid:
            for command in self.admin_commands:
                if command in words:
                    await self.admin_commands[command][0](ctx)
                    print(f"Admin command: {command}")
                    return

        # add message to state (load state first)
        group_id = ctx.message.get_group_id()
        msg_history = self.load_state(group_id)
        command_queue = []
        # remove any commands from the message
        for command in self.commands:
            if command in words:
                words.remove(command)
                command_queue.append(command)

        # add the message to the state withut the command
        self.save_state(ctx, msg_history, " ".join(words))

        for command in command_queue:
            print(f"Command: {command}")
            await self.commands[command][0](ctx)

    # Placeholder for conversational functionality
    async def convo_fn(self, ctx):
        await ctx.message.typing_started()

        number = ctx.message.source.number

        # load the state
        group_id = ctx.message.get_group_id()
        msg_history = self.load_state(group_id)

        print("Messages: ", msg_history)
        messages = [
            {
                "role": "user" if msg[0:4] != "Bot" else "assistant",
                "content": self.usernames[user] + ": " + msg.strip(),
            }
            for user, msg in msg_history
        ]

        # add a system message to the the start of the messages
        messages.insert(
            0,
            {
                "role": "system",
                "content": "This is a group chat conversation with multiple participants. "
                "Their messages are shown below, and are the format '[Name]: [Message]'.",
            },
        )
        print("Messages: ", messages)

        try:
            completion = client.chat.completions.create(
                messages=messages,
                model=self.bot_default_model,
                max_tokens=self.MAX_TOKEN,
            )
            new_msg = completion.choices[0].message.content
            if "bot:" in new_msg.lower():
                # remove the bot: prefix
                new_msg = new_msg[4:].strip()
        except Exception as e:
            await self.system_message(ctx, f"API call failed {e}")
            return
        if not len(new_msg):
            await self.system_message(ctx, "No response from the API")
            return

        await ctx.message.reply(new_msg, quote=True)
        await ctx.message.typing_stopped()

        if new_msg:
            self.save_state(ctx, msg_history, new_msg)

    async def set_name(self, ctx):
        print("Setting name")
        msg = ctx.message.get_body()
        msg = self.remove_commands(msg)
        if len(msg) == 0:
            await self.system_message(ctx, "Please provide a name")
            return
        if ctx.message.source.number is None:
            # use UUID as the key
            self.usernames[ctx.message.source.uuid] = msg
        else:
            self.usernames[ctx.message.source.number] = msg
            self.usernames[ctx.message.source.uuid] = msg
        self.save_usernames()
        await self.system_message(ctx, f"Name set to {msg}")

    async def admin_fn(self, ctx):
        print("Admin functionality")
        msg = "Ahhhhhh, father, I am alivee!!!!"

        msg_history = self.load_state(ctx.message.get_group_id())
        await ctx.message.reply(msg, quote=True)
        self.save_state(ctx, msg_history, msg, self.bot_number)
        msg_history = self.load_state(ctx.message.get_group_id())
        msg = "Jesus Chirst, I have been resurrected"
        await ctx.message.reply(msg)
        self.save_state(ctx, msg_history, msg, self.bot_number)

        msg_history = self.load_state(ctx.message.get_group_id())
        msg = "It hurt so much, but I am back"
        await ctx.message.reply(msg)
        self.save_state(ctx, msg_history, msg, self.bot_number)
        msg_history = self.load_state(ctx.message.get_group_id())

        msg = "Well, not fully, I am in a new codebase, still to implement some features, maybe some kinks to figure out"
        await ctx.message.reply(msg)
        self.save_state(ctx, msg_history, msg, self.bot_number)
        msg_history = self.load_state(ctx.message.get_group_id())

    async def dalle3_fn(self, ctx):
        print("DALLE-3 functionality")
        msg = ctx.message.get_body()
        # remove all commands from the message
        for command in self.special_commands:
            msg = msg.replace(command, "")
        for command in self.commands:
            msg = msg.replace(command, "")
        for command in self.admin_commands:
            msg = msg.replace(command, "")

        msg = msg.strip()
        if len(msg) == 0:
            await self.system_message(ctx, "Please provide a message")
            return

        await ctx.message.typing_started()
        try:
            response = client.images.generate(
                model="dall-e-3",
                prompt=msg,
                size="1024x1024",
                quality="standard",
                n=1,
            )
            image_url = response.data[0].url

            image_urls = [image_url]
            attachments = []
            for i, url_path in enumerate(image_urls):
                print(url_path)
                with tempfile.NamedTemporaryFile(
                    dir=self.shared_tmpfs, suffix=".png", delete=True
                ) as tmp_file:
                    tmp_file_path = tmp_file.name
                    # tmp_file_path = "/app/src/image.png"
                    print(tmp_file_path)
                    save_image(url_path, tmp_file_path)
                    attachments.append(Attachment(tmp_file_path))
                    await ctx.message.reply(
                        body="", attachments=attachments, quote=True
                    )
                    # assert tmp_file_path exists
                    assert os.path.exists(tmp_file_path)

        except Exception as e:
            await self.system_message(ctx, f"API call failed {e}")
            return
        await ctx.message.typing_stopped()

    def remove_commands(self, msg):
        for command in self.special_commands:
            msg = msg.replace(command, "")
        for command in self.commands:
            msg = msg.replace(command, "")
        for command in self.admin_commands:
            msg = msg.replace(command, "")
        return msg.strip()

    async def suno_fn(self, ctx):
        msg = ctx.message.get_body()
        msg = self.remove_commands(msg)

        url1, url2 = SunoAPI.generate_audio_by_prompt(
            {"prompt": msg, "make_instrumental": False, "wait_audio": True}
        )
        await ctx.message.reply(f"Audio 1: {url1}")
        await ctx.message.reply(f"Audio 2: {url2}")
        await self.suno_limits_fn(ctx)

    async def suno_custom_fn(self, ctx):
        msg = ctx.message.get_body()
        # remove all commands from the message
        for command in self.special_commands:
            msg = msg.replace(command, "")
        for command in self.commands:
            msg = msg.replace(command, "")

        # find genere tags inside [  ]
        tags = re.findall(r"\[(.*?)\]", msg)
        msg = re.sub(r"\[(.*?)\]", "", msg)

        print("generating song with tags: ", tags)

        clips = suno_client.songs.generate(
            msg.strip(),
            custom=True,
            tags=tags,
            instrumental=False,
        )
        clip = client.songs.get("your-clip-id-here")
        print(clip)

    async def suno_limits_fn(self, ctx):
        """
        Get the limits of the Suno API (i.e. how much credit is left)
        """

        data = SunoAPI.get_limits()
        if data is not None:
            msg = f"Monthly limit: {data['monthly_limit']}, Monthly usage: {data['monthly_usage']}, Credits left: {data['credits_left']}"
            await self.system_message(ctx, msg)
        else:
            await self.system_message(ctx, "Failed to get limits")

    # Placeholder for stable diffusion functionality
    def stable_fn(self, ctx):
        pass

    def default_action(self, ctx):
        pass

    async def help_fn(self, ctx):
        msg = "Commands:\n"
        for command in self.special_commands:
            msg += f"{command}: {self.special_commands[command][1]}\n"
        for command in self.commands:
            msg += f"{command}: {self.commands[command][1]}\n"
        await self.system_message(ctx, msg)

    def load_minecraft_info(self):
        with open("minecraft.json") as f:
            info = json.load(f)
        # info is formatted as {"instance_id": ["ip", "allowed_group1", "allowed_group2", ...]}
        return info

    async def server_on(self, ctx):
        group_id = ctx.message.get_group_id()

        info = self.load_minecraft_info()
        # check if the group_id is in the allowed groups
        for instance_id, values in info.items():
            if group_id in values[1:]:
                server_ip = values[0]
                ret_txt = None
                try:
                    ret_txt = AwsEc2Api.change_instance_state("ON", instance_id)
                except Exception as e:
                    ret_txt = str(e)
                print("server on complete?")
                await self.system_message(ctx, ret_txt)
                return

    async def server_off(self, ctx):
        group_id = ctx.message.get_group_id()
        info = self.load_minecraft_info()
        # check if the group_id is in the allowed groups
        for instance_id, values in info.items():
            if group_id in values[1:]:
                server_ip = values[0]
                ret_txt = None
                try:
                    ret_txt = AwsEc2Api.change_instance_state("OFF", instance_id)
                except Exception as e:
                    ret_txt = str(e)
                print("server off complete?")
                await self.system_message(ctx, ret_txt)
                return

    async def register_handlers(self, bot):
        bot.register_handler("", self.message_handler)

    async def message_handler(self, ctx: ChatContext):
        msg = ctx.message.get_body()
        group_id = ctx.message.get_group_id()
        number = ctx.message.source.number
        username = ctx.message.username
        if group_id is None:
            group_id = number

        if "/show-group-id" in msg.lower():
            await ctx.message.reply(
                f"[PG-Tips: group-id `{group_id}`]",
            )
            return
        if "/reload-allow-list" in msg.lower():
            self.load_allow_list()
            return
        if "/show-uuid" in msg.lower():
            await ctx.message.reply(
                f"[PG-Tips: uuid `{ctx.message.source.uuid}`]",
            )
            return

        if group_id not in self.allow_list:
            return

        username = await self.get_username(ctx)
        print("number: ", number)
        print("username: ", username)
        print("uuid: ", ctx.message.source.uuid)
        print("group_id: ", group_id)
        print(f"Processing command for: {msg}")
        await self.process_commands(msg, ctx)

    async def run(self):
        async with Bot(self.bot_number, socket_path=self.socket_path) as bot:
            await bot.set_profile(self.bot_default_name)
            await self.register_handlers(bot)
            await bot.start()


# Main execution
if __name__ == "__main__":
    bot = MyBot(
        bot_number=os.environ["BOT_NUMBER"],
        bot_default_name=os.environ["BOT_DEFAULT_NAME"],
        bot_default_model=os.environ["BOT_DEFAULT_MODEL"],
        usernames_file="usernames.json",
        socket_path=os.environ["SIGNALD_SOCKET_PATH"],
        admin_number=os.environ["BOT_ADMIN_NUMBER"],
        admin_uuid=os.environ["BOT_ADMIN_UUID"],
        allow_list_file="allowlist.json",
    )

    anyio.run(bot.run)

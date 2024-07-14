import discord
from discord import app_commands
from discord.ui import Button, View
from discord.ext import commands
import dotenv
import json
import os
from Levenshtein import distance

dotenv.load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
activity = discord.Game(name="Hosting Quizzes..")
bot = commands.Bot(command_prefix="$", intents=intents, activity=activity)
client = bot

with open('questions.json') as f:
    questions = json.load(f)

current_question = None
score = {}
answered = {}
answered_right = []


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')
    await bot.tree.sync()


@client.event
async def on_message(message):
    if message.author == client.user:
        return
    if current_question and current_question["type"] == "guess":
        await handle_guess_answer(message)
    elif current_question and current_question["type"] == "multi":
        await handle_multiple_answer(message)


wrong_embed = discord.Embed(
    title="Wrong Answer", description="Your answer is WRONG!", color=discord.Color.red()
)
correct_embed = discord.Embed(
    title="Correct Answer", description="Your answer is RIGHT!", color=discord.Color.green()
)
already_answered = discord.Embed(
    title="Already Answered", description="You have already answered this question!", color=discord.Color.red()
)
question_closed = discord.Embed(
    title="Question Closed", description="This question has already been answered correctly.", color=discord.Color.red()
)


class QuestionView(View):
    def __init__(self, question):
        super().__init__(timeout=180.0)
        self.question = question
        self.message = None  # Initialize the message attribute

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)

    async def answer_check(self, interaction: discord.Interaction):
        if interaction.user.id in answered:
            await interaction.response.send_message(embed=already_answered, ephemeral=True)
            return
        answered[interaction.user.id] = True
        if interaction.data['custom_id'] == self.question['answer']:
            await interaction.response.send_message(embed=correct_embed, ephemeral=True)
            await self.close_question(interaction)
        else:
            wrong_embed.add_field(
                name="The Correct Answer is:", value=self.question['answer'])
            await interaction.response.send_message(embed=wrong_embed, ephemeral=True)

    async def close_question(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True
        if self.message:
            await self.message.edit(view=self)
        global current_question
        current_question = None  # Reset the current question
        answered = {}


@bot.hybrid_command(name="question", description="Asks a Question from the set.")
@app_commands.describe(ques_type="Type of question")
async def ask_question(ctx, ques_type: str):
    global current_question
    for question in questions:
        if question['type'] == ques_type:
            current_question = question
            break
    question_text = current_question["question"]

    if ques_type == "mcq":
        global answered
        answered = {}
        view = QuestionView(current_question)
        embed = discord.Embed(
            title="Question", description=question_text, color=discord.Color.greyple())

        for answer in current_question["options"]:
            btn = Button(
                label=answer, style=discord.ButtonStyle.primary, custom_id=answer)
            btn.callback = view.answer_check
            view.add_item(btn)

        message = await ctx.send(embed=embed, view=view)
        view.message = message  # Save the message object to the view for editing
    elif ques_type == "guess":
        embed = discord.Embed(
            title="Question", description=question_text, color=discord.Color.greyple())
        embed.add_field(name="Answer", value="Type your answer in the chat.")
    elif ques_type == "multi":
        embed = discord.Embed(
            title="Question", description=question_text, color=discord.Color.greyple())
        await ctx.send(embed=embed)


async def handle_guess_answer(message):
    global current_question
    guess = message.content.lower()
    correct = current_question["answer"]
    dist = distance(guess, correct.lower())
    if dist/(len(correct)) <= 0.2:
        await message.reply(embed=correct_embed)
        embed = discord.Embed(
            title="Correct Answer", description=f"{message.author} got the correct answer!", color=discord.Color.green()
        )
        embed.add_field(name="Correct Answer:", value=correct)
        await message.channel.send(embed=embed)
        current_question = None


async def handle_multiple_answer(message):
    global current_question, answered_right
    answered[message.author.id] = True
    for word in [message.content.strip()]:
        for num, answer in enumerate(current_question['answer']):
            if answer not in answered_right:
                correct = answer
                dist = distance(word.lower(), correct.lower())
                if dist/(len(correct)) <= 0.2:
                    await message.reply(embed=correct_embed)
                    embed = discord.Embed(
                        title="Correct Answer", description=f"{message.author.mention} got part {num+1} of the question right!", color=discord.Color.green()
                    )
                    embed.add_field(name="Answer:", value=correct)
                    answered_right.append(correct)
                    await message.channel.send(embed=embed)
                    if len(answered_right) == len(current_question['answer']):
                        answered_right = []
                        embed = discord.Embed(
                            title="Question Complete", description=f"The question has been answered!", color=discord.Color.green()
                        )
                        await message.channel.send(embed=embed)
                        current_question = None
                    return


@bot.hybrid_command(name="answer", description="Submit your Answer to the question")
@app_commands.describe(ans="Answer to the question")
async def submit_answer(ctx, ans: str):
    global current_question
    if current_question["type"] == "guess":
        guess = ans.lower()
        correct = current_question["answer"]
        dist = distance(guess, correct.lower())
        if dist/(len(correct)) <= 0.2:
            embed = correct_embed
            embed.add_field(
                name=f"{ctx.author}'s Answer:", value=ans)
            await ctx.send(embed=embed)
            current_question = None
        else:
            embed = wrong_embed
            embed.add_field(
                name=f"{ctx.author}'s Answer:", value=ans)
            await ctx.send(embed=embed)
    else:
        await ctx.send("This command is only for Guess type questions.")


@bot.hybrid_command(name="new", description="Add a new question to the set.")
@app_commands.describe(ques_type="Type of question", question="The question text", options="Options for MCQ (comma separated)", answer="The correct answer")
async def add_question(ctx, ques_type: str, question: str, options: str = None, answer: str = None):
    global questions
    new_question = {
        "type": ques_type,
        "question": question,
        "answer": answer
    }
    if ques_type == "mcq":
        new_question["options"] = options.split(',')

    questions.append(new_question)
    with open('questions.json', 'w') as f:
        json.dump(questions, f, indent=4)

    await ctx.send("New question added successfully.")


@bot.hybrid_command(name="ask", description="Ask a question directly without adding to the set.")
@app_commands.describe(ques_type="Type of question", question="The question text", image_url="URL of the image", options="Options for MCQ (comma separated)", answers="The correct answer")
async def ask_direct_question(ctx, ques_type: str, question: str, image_url: str = None, options: str = None, answers: str = None):
    global current_question
    if ques_type == "mcq":
        current_question = {
            "type": ques_type,
            "question": question,
            "answer": answers
        }
        current_question["options"] = options.split(',')
        global answered
        answered = {}
        view = QuestionView(current_question)
        embed = discord.Embed(
            title="Question", description=question, color=discord.Colour(0x1d1e21))
        if image_url:
            embed.set_image(url=image_url)
        for ans in current_question["options"]:
            btn = Button(
                label=ans, style=discord.ButtonStyle.primary, custom_id=ans)
            btn.callback = view.answer_check
            view.add_item(btn)
        await ctx.send("Sending the question...", ephemeral=True, delete_after=3)
        message = await ctx.channel.send(embed=embed, view=view)
        view.message = message  # Save the message object to the view for editing
    elif ques_type == "guess":
        current_question = {
            "type": ques_type,
            "question": question,
            "answer": answers
        }
        embed = discord.Embed(
            title="Question", description=question, color=discord.Colour(0x1d1e21))
        if image_url:
            embed.set_image(url=image_url)
        await ctx.send("Sending the question...", ephemeral=True, delete_after=3)
        await ctx.channel.send(embed=embed)
    elif ques_type == "multi":
        current_question = {
            "type": ques_type,
            "question": question,
            "answer": [answer.strip() for answer in answers.split(',')]
        }
        embed = discord.Embed(
            title="Question", description=question, color=discord.Colour(0x1d1e21))
        if image_url:
            embed.set_image(url=image_url)
        await ctx.send("Sending the question...", ephemeral=True, delete_after=3)
        await ctx.channel.send(embed=embed)

client.run(os.getenv('TOKEN'))

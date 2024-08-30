import os
import streamlit as st
import google.generativeai as genai
from openai import OpenAI
import io
import json
from PIL import Image
from dotenv import load_dotenv, find_dotenv
import requests
import shutil
# import IPython.display as ipd

# Load environment variables
load_dotenv(find_dotenv(), override=True)
genai.configure(api_key=os.environ.get('GOOGLE_API_KEY'))
openai_api_key = os.environ.get('OPENAI_API_KEY')
client = OpenAI(api_key=openai_api_key)

# Load the knowledge base JSON file


def load_knowledge_base():
    with open('knowledge_base.json', 'r') as file:
        knowledge = json.load(file)
    return knowledge


knowledge = load_knowledge_base()

# Calculate TDEE based on user input


def calculate_tdee(weight, height, age, gender, activity_level):
    gender_key = gender.capitalize()
    bmr_formula = knowledge['caloric_needs']['bmr_formulas'][gender_key]
    bmr = eval(bmr_formula, {"weight": weight, "height": height, "age": age})
    activity_factor = knowledge['caloric_needs']['activity_factors'][activity_level.lower(
    ).replace(" ", "_")]
    return bmr * activity_factor

# Function to process image and generate answers using Gemini


def analyze_fridge_contents(img):
    model = genai.GenerativeModel('gemini-1.5-flash')
    response = model.generate_content(["List the items in this fridge", img])
    return response.text

# Convert Streamlit image input to PIL format


def st_image_to_pil(st_image):
    image_data = st_image.read()
    pil_image = Image.open(io.BytesIO(image_data))
    return pil_image

# Function to create meal plan based on ingredients


def create_meal_plan(ingredients, tdee, user_preferences, knowledge):
    prompt = f'''
    Create a healthy daily meal plan for breakfast, lunch, and dinner based on the following ingredients: ```{ingredients}```.
    Your output should be in the text format.
    Follow the instructions below carefully.
    ##Instructions:##
    <instructions>
    1. {'Use ONLY the provided ingredients with salt, pepper, and spices.' if user_preferences['exact_ingredients'] else 'Feel free to incorporate the provided ingredients as a base and add other ingredients if you consider them necessary to enhance the flavor, nutritional value, or overall appeal of the recipes.'}
    2. Specify the exact amount of each ingredient.
    3. Ensure that the total daily calorie intake is below {tdee}.
    4. For each meal (breakfast, lunch, dinner), explain the recipe step by step.
    5. For each meal, specify the total number of calories and the number of servings.
    6. For each meal, provide a concise title that summarizes the main ingredients and flavors.
    7. For each recipe, indicate the prep, cook, and total time.
    8. Incorporate the following user preferences:
       - Age: {user_preferences['basic_info']['age']}
       - Gender: {user_preferences['basic_info']['gender']}
       - Weight: {user_preferences['basic_info']['weight']} kg
       - Height: {user_preferences['basic_info']['height']} cm
       - Activity level: {user_preferences['basic_info']['activity_level']}
       - Allergies: {', '.join(user_preferences['dietary_restrictions']['allergies']) if user_preferences['dietary_restrictions']['allergies'] else 'None'}
       - Dietary preference: {user_preferences['dietary_restrictions']['diet_preference']}
       - Health goal: {user_preferences['health_goal']}
       - Cooking skill level: {user_preferences['cooking_skill']}
       - Maximum preparation time: {user_preferences['max_prep_time']} minutes
       - Preferred cuisines: {', '.join(user_preferences['flavor_preferences']['cuisines']) if user_preferences['flavor_preferences']['cuisines'] else 'Any'}
       - Spice preference (1-5): {user_preferences['flavor_preferences']['spice_level']}
    9. Incorporate the following guidelines from the knowledge base:
       - Recommended foods: {knowledge['food_guidelines']['recommended_foods']}
       - Foods to avoid: {knowledge['food_guidelines']['foods_to_avoid']}
       - Cooking methods: {knowledge['food_guidelines']['cooking_methods']}
       - Macronutrient ratios: {knowledge['macronutrient_guidelines']['ratios']}
       - Protein goal: {knowledge['macronutrient_guidelines']['protein_goal']}
    10. Adjust the meals based on the user's health goal:
        - For weight loss: Focus on lower-calorie, nutrient-dense foods
        - For muscle gain: Increase protein content and overall calories
        - For maintenance: Balance macronutrients according to the knowledge base guidelines
        - For general wellness: Focus on a variety of nutrient-rich foods
    11. Adapt recipes to the user's cooking skill level:
        - For beginners: Use simple cooking methods and fewer ingredients
        - For intermediate: Incorporate more diverse ingredients and cooking techniques
        - For advanced: Include more complex recipes and preparation methods
    12. Ensure all recipes can be prepared within the specified maximum preparation time.
    13. Incorporate the user's preferred cuisines and spice level into the recipes.
    14. Strictly avoid any ingredients the user is allergic to.
    15. Adhere to the user's dietary preference (e.g., vegan, vegetarian, keto) when selecting ingredients.
    16. Separate the recipes with EXACTLY 50 dashes (-).
    </instructions>

    The last line of your answer should be a string containing ONLY the titles of the recipes (breakfast, lunch, dinner) with a comma in between.
    '''
    response = client.chat.completions.create(
        model="gpt-4-0125-preview",
        messages=[
            {'role': 'system', 'content': 'You are a skilled cook with the expertise of a chef and a nutritionist.'},
            {'role': 'user', 'content': prompt}
        ],
        temperature=1
    )
    return response.choices[0].message.content
# Function to create and save image for a recipe


def create_and_save_image(title, extra=''):
    image_prompt = f'{title}, hd quality, {extra}'
    response = client.images.generate(
        model="dall-e-3",
        prompt=image_prompt,
        style='natural',
        size="1024x1024",
        quality="standard"
    )

    image_url = response.data[0].url
    image_resource = requests.get(image_url, stream=True)
    image_filename = f'{title}.png'

    if image_resource.status_code == 200:
        with open(image_filename, 'wb') as f:
            shutil.copyfileobj(image_resource.raw, f)
        return image_filename
    else:
        print('Error accessing the image!')
        return False

# Function to generate speech for a recipe


def generate_speech(recipe, filename):
    response = client.audio.speech.create(
        model='tts-1',
        voice='alloy',
        input=recipe
    )
    with open(filename, 'wb') as f:
        f.write(response.content)


def get_user_preferences():
    st.sidebar.header("User Profile and Preferences")

    # Basic Information
    st.sidebar.subheader("Basic Information")
    age = st.sidebar.number_input('Age', min_value=10, max_value=100, value=30)
    gender = st.sidebar.selectbox('Gender', ['Male', 'Female', 'Other'])
    weight = st.sidebar.number_input(
        'Weight (kg)', min_value=30, max_value=200, value=70)
    height = st.sidebar.number_input(
        'Height (cm)', min_value=100, max_value=250, value=175)
    activity_level = st.sidebar.selectbox('Activity Level',
                                          ['Sedentary', 'Lightly Active', 'Moderately Active', 'Very Active'])

    # Dietary Restrictions
    st.sidebar.subheader("Dietary Restrictions")
    allergies = st.sidebar.multiselect('Allergies',
                                       ['Nuts', 'Dairy', 'Eggs', 'Soy', 'Wheat', 'Fish', 'Shellfish'])
    diet_preference = st.sidebar.selectbox('Dietary Preference',
                                           ['Omnivore', 'Vegetarian', 'Vegan', 'Pescatarian', 'Keto', 'Paleo'])

    # Health Goals
    st.sidebar.subheader("Health Goals")
    health_goal = st.sidebar.selectbox('Health Goal',
                                       ['Weight loss', 'Muscle gain', 'Maintenance', 'General wellness'])

    # Cooking Skills
    st.sidebar.subheader("Cooking Skills")
    cooking_skill = st.sidebar.selectbox('Cooking Skill Level',
                                         ['Beginner', 'Intermediate', 'Advanced'])

    # Time Constraints
    st.sidebar.subheader("Time Constraints")
    max_prep_time = st.sidebar.slider(
        'Maximum Meal Prep Time (minutes)', 15, 120, 30)

    # Flavor Preferences
    st.sidebar.subheader("Flavor Preferences")
    cuisines = st.sidebar.multiselect('Preferred Cuisines',
                                      ['Italian', 'Mexican', 'Asian', 'Mediterranean', 'American', 'Indian'])
    spice_level = st.sidebar.slider('Spice Preference', 1, 5, 3)

    st.sidebar.subheader("Ingredient Usage")
    exact_ingredients = st.sidebar.checkbox(
        'Use only provided ingredients (plus salt, pepper, and spices)')

    return {
        'basic_info': {
            'age': age,
            'gender': gender,
            'weight': weight,
            'height': height,
            'activity_level': activity_level
        },
        'dietary_restrictions': {
            'allergies': allergies,
            'diet_preference': diet_preference
        },
        'health_goal': health_goal,
        'cooking_skill': cooking_skill,
        'max_prep_time': max_prep_time,
        'flavor_preferences': {
            'cuisines': cuisines,
            'spice_level': spice_level
        },
        'exact_ingredients': exact_ingredients
    }
# Main Streamlit app


def main():
    st.image('SmartPlate.png')
    st.subheader('Fridge Content Analysis & Recipe Suggestion ✨')

    # Get all user preferences
    user_preferences = get_user_preferences()

    # File uploader for fridge image
    img = st.file_uploader('Select an Image of Your Fridge:', type=[
                           'jpg', 'jpeg', 'png', 'gif'])

    if img:
        st.image(img, caption='Uploaded Fridge Image.')
        pil_image = st_image_to_pil(img)

        # Analyze fridge contents
        with st.spinner('Analyzing fridge contents...'):
            detected_items = analyze_fridge_contents(pil_image)
        st.write("Detected items:", detected_items)

        # Calculate TDEE
        tdee = calculate_tdee(user_preferences['basic_info']['weight'],
                              user_preferences['basic_info']['height'],
                              user_preferences['basic_info']['age'],
                              user_preferences['basic_info']['gender'],
                              user_preferences['basic_info']['activity_level'])
        st.write(f"Calculated TDEE: {tdee:.2f} calories/day")

        # Generate meal plan
        with st.spinner('Generating meal plan...'):
            meal_plan = create_meal_plan(
                detected_items, tdee, user_preferences, knowledge)

        # Display meal plan
        meals = meal_plan.split('-' * 50)
        titles = meal_plan.splitlines()[-1].split(',')
        titles = [t.strip(" '") for t in titles]

        for i, (meal, title) in enumerate(zip(meals[:-1], titles)):
            st.subheader(f"Meal {i+1}: {title}")
            st.write(meal)

            # Generate and display image
            with st.spinner(f'Generating image for {title}...'):
                image_filename = create_and_save_image(
                    title, extra='white background')
                if image_filename:
                    st.image(image_filename, caption=title)

            # Generate and play audio
            audio_filename = f'{title}.mp3'
            with st.spinner(f'Generating audio for {title}...'):
                generate_speech(meal, audio_filename)
                st.audio(audio_filename)


if __name__ == '__main__':
    main()

# Next steps:
# base recipe from knowledge, add allergies, etc. add nutrition per food.

import os
import json
import time
import streamlit as st
from google import genai
from google.genai import types

# --- Configuration and Setup ---

# IMPORTANT: The user has provided an API key for immediate use in this script.
# We will use the provided key as a fallback if the environment variable is not set.
# User-provided Key: AIzaSyAfX5tJn6tg1323-uXUZke6-G96_1uYp4s
API_KEY = os.environ.get("GEMINI_API_KEY", "AIzaSyAfX5tJn6tg1323-uXUZke6-G96_1uYp4s")

# Exponential backoff parameters for API calls
MAX_RETRIES = 5
INITIAL_DELAY = 1

# --- Structured Output Schema for the Itinerary ---
ITINERARY_SCHEMA = types.Schema(
    type=types.Type.ARRAY,
    description="A list of daily itinerary plans.",
    items=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "day": types.Schema(type=types.Type.INTEGER, description="The day number, starting from 1."),
            "theme": types.Schema(type=types.Type.STRING, description="A short, catchy theme for the day (e.g., 'Historical Walking Tour', 'Cheap Eats Day')."),
            "plan": types.Schema(
                type=types.Type.ARRAY,
                description="List of activities for the day.",
                items=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "time": types.Schema(type=types.Type.STRING, description="Time slot (e.g., 'Morning', 'Lunch', 'Afternoon', 'Evening')."),
                        "activity": types.Schema(type=types.Type.STRING, description="The specific activity or location."),
                        "estimated_cost_usd": types.Schema(type=types.Type.NUMBER, description="Estimated cost for the activity in USD (use 0 for free activities).")
                    },
                    required=["time", "activity", "estimated_cost_usd"]
                )
            ),
            "efficiency_tip": types.Schema(type=types.Type.STRING, description="A practical, budget-focused tip for minimizing travel time or cost, focusing on walking/public transport.")
        },
        required=["day", "theme", "plan", "efficiency_tip"]
    )
)

# --- Core Functionality: AI Generation ---

def generate_student_itinerary(destination, days, interests):
    """
    Connects to the Gemini API to generate a structured, budget-friendly itinerary.
    Implements exponential backoff for robust API calling, providing detailed errors on failure.
    """
    if not API_KEY:
        return "Error: GEMINI_API_KEY is missing. Please set it as an environment variable.", None

    try:
        client = genai.Client(api_key=API_KEY)
    except Exception as e:
        return f"Error initializing Gemini client: {e}", None

    system_instruction = (
        "You are a World-Class Budget Student Travel Expert and Route Planner. "
        "Your goal is to create a detailed, efficient, and fun travel plan for a student with limited funds. "
        "All suggestions MUST prioritize free or low-cost activities (under $20 USD). "
        "You must return the response as a valid JSON object matching the provided schema. "
        "Provide specific cost estimates for each activity in USD. "
        "For the 'efficiency_tip', focus on grouping nearby locations to minimize travel or suggesting budget public transport passes."
    )

    user_query = (
        f"Generate a {days}-day travel itinerary for a trip to {destination}. "
        f"The total budget is restricted (focus on lowest costs). "
        f"The student is interested in: {interests}. "
        "Ensure the plan is efficient to follow, grouping activities by location."
    )

    generation_config = types.GenerateContentConfig(
        system_instruction=system_instruction,
        response_mime_type="application/json",
        response_schema=ITINERARY_SCHEMA,
        # Note: Tool use (Google Search) is incompatible with structured JSON output, so it has been removed.
    )

    last_error = "Unknown error occurred before first API call."
    
    for attempt in range(MAX_RETRIES):
        try:
            # print(f"Attempting to generate itinerary (Attempt {attempt + 1})...")
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[user_query],
                config=generation_config,
            )

            # Successfully received response, now try to parse it
            try:
                itinerary_json = json.loads(response.text)
                return "Itinerary generated successfully!", itinerary_json
            except json.JSONDecodeError as e:
                # Store error for AI generation failure
                last_error = f"AI response format error (Day {attempt+1}): Failed to parse JSON response. Details: {e}"
                
        except Exception as e:
            # Store error for connection/authentication/rate limit failure
            last_error = f"Gemini API connection error (Day {attempt+1}): {e}"

        # Exponential Backoff
        if attempt < MAX_RETRIES - 1:
            delay = INITIAL_DELAY * (2 ** attempt)
            time.sleep(delay)
            # Suppress detailed console logging for clean Streamlit output

    # Final return after all retries have failed
    return f"Failed to generate itinerary after multiple retries. Last known error: {last_error}", None

# --- Display Utility (Streamlit specific) ---

def display_itinerary_streamlit(itinerary):
    """Renders the structured itinerary using Streamlit components."""
    if not itinerary:
        return

    total_cost = sum(
        sum(activity.get("estimated_cost_usd", 0) for activity in day_plan.get("plan", []))
        for day_plan in itinerary
    )

    st.header("✨ Your Personalized Travel Itinerary")
    st.markdown(f"**Total Estimated Cost (Activities Only):** **${total_cost:.2f}**")
    st.markdown("_Note: This excludes flights, accommodation, and general food._")

    for day_plan in itinerary:
        day_num = day_plan.get("day", "N/A")
        theme = day_plan.get("theme", "No Theme")
        plan = day_plan.get("plan", [])
        tip = day_plan.get("efficiency_tip", "No tip provided.")

        daily_cost = sum(activity.get("estimated_cost_usd", 0) for activity in plan)

        with st.expander(f"📅 Day {day_num}: {theme} (Cost: ${daily_cost:.2f})", expanded=True):
            
            # Display activities in a clean table format
            activities_data = [
                {
                    "Time": activity.get("time", "N/A"),
                    "Activity": activity.get("activity", "N/A"),
                    "Cost (USD)": f"${activity.get('estimated_cost_usd', 0):.2f}"
                }
                for activity in plan
            ]
            st.table(activities_data)

            st.info(f"**🚌 Efficiency Tip:** {tip}")

# --- Main Streamlit App Logic ---

def main():
    st.set_page_config(
        page_title="AI Student Travel Planner",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    st.title("✈️ AI Student Travel Planner")
    st.markdown("### Personalized, Budget-Friendly Itineraries Powered by Gemini")

    # Check for API Key at startup
    if not API_KEY:
        st.error("🚨 CRITICAL ERROR: The GEMINI_API_KEY is not set. The planner will not function.")
        return

    # User Input Form
    with st.form("travel_form"):
        st.subheader("Plan Your Budget Trip")
        
        destination = st.text_input("Destination (City, Country)", help="E.g., Rome, Italy", key="destination")
        days = st.number_input("Number of Days", min_value=1, max_value=14, value=3, key="days")
        interests = st.text_area("Main Interests", 
                                 help="E.g., history, cheap food, local markets, photography", 
                                 key="interests")
        
        submitted = st.form_submit_button("Generate Budget Itinerary")

    if submitted:
        if not all([destination, days, interests]):
            st.warning("Please fill in all the required fields.")
            return

        with st.spinner("🧠 Generating your optimized itinerary... This may take a moment."):
            # 2. Generate Itinerary
            status_message, itinerary_data = generate_student_itinerary(
                destination=destination,
                days=days,
                interests=interests
            )

        # 3. Display Results
        if "successfully" in status_message:
            st.success(status_message)
            display_itinerary_streamlit(itinerary_data)
        else:
            # Display the more detailed error message
            st.error(status_message)


if __name__ == "__main__":
    main()
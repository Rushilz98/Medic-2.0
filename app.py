import os
import json
import joblib
import numpy as np
import warnings
from flask import Flask, render_template, request, jsonify
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up Flask app
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key')

# ===========================
# SUPPRESS WARNINGS
# ===========================
warnings.filterwarnings('ignore')

# ===========================
# LOAD THE TRAINED MODEL
# ===========================
try:
    # Get absolute path to model file
    model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'comprehensive_disease_diagnosis_model.pkl')
    
    # Load your trained model
    model_data = joblib.load(model_path)
    
    # Extract model components
    tier1_model = model_data['tier1_model']
    tier2_model = model_data['tier2_model']
    le = model_data['label_encoder']
    symptoms = model_data['symptoms']
    category_map = model_data['disease_category_map']
    
    print("✅ Model loaded successfully!")
    print(f"Can diagnose {len(le.classes_)} disease conditions")
    print(f"Using {len(symptoms)} symptoms for diagnosis")
    
except Exception as e:
    print(f"❌ CRITICAL ERROR loading model: {str(e)}")
    tier1_model = None
    tier2_model = None
    le = None
    symptoms = []
    category_map = {}
    # Don't crash the app - just show a warning
    print("⚠️ WARNING: Model failed to load. The app will run but disease prediction won't work.")

# ===========================
# SYMPTOM OUTPUT SCHEMA
# ===========================
class SymptomOutput(BaseModel):
    symptoms: list[str] = Field(description="List of exact symptom names matched from the predefined list")

# ===========================
# SYMPTOM MAPPER USING LLM
# ===========================
def create_symptom_mapper():
    """Creates a chain that maps natural language symptoms to exact symptom names"""
    
    # Get Google API key from environment (loaded from .env)
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("Google API key not configured. Please set GOOGLE_API_KEY in your .env file")
    
    # Create the prompt template with improved instructions
    prompt_template = """You are a medical symptom mapper. Convert casual symptom descriptions to EXACT symptom names from this list:

{symptoms}

STRICT RULES:
- ONLY return symptoms that EXACTLY match the list above
- NEVER modify, abbreviate, or create new symptom names
- RETURN ONLY JSON with key "symptoms" containing matched symptom names
- IGNORE symptoms that don't have an EXACT match
- DO NOT add explanations or greetings

Example input: "I've been having trouble catching my breath and my chest feels tight"
Example output: {{"symptoms": ["shortness of breath", "chest tightness"]}}

Example input: "I feel dizzy and I can't sleep well at night"
Example output: {{"symptoms": ["dizziness", "insomnia"]}}

Example input: "My heart is racing"
Example output: {{"symptoms": ["increased heart rate"]}}

Now process this input:
{user_input}"""

    # Set up the prompt
    prompt = PromptTemplate(
        template=prompt_template,
        input_variables=["user_input", "symptoms"]
    )
    
    # Initialize the Gemini model
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=0.1,
        google_api_key=api_key,
        max_retries=3
    )
    
    # Set up the output parser
    output_parser = JsonOutputParser(pydantic_object=SymptomOutput)
    
    # Create the chain
    chain = prompt | llm | output_parser
    
    return chain

def map_symptoms(user_input):
    """Map casual symptom descriptions to exact symptom names using LLM"""
    
    # Format the symptoms list for the prompt (simplified format)
    symptoms_str = "\n".join([f"- {symptom}" for symptom in symptoms])
    
    try:
        # Get Google API key from environment
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return {"symptoms": [], "error": "Google API key is missing"}
        
        # Create the symptom mapper chain
        symptom_mapper = create_symptom_mapper()
        
        # Get the mapped symptoms
        result = symptom_mapper.invoke({
            "user_input": user_input,
            "symptoms": symptoms_str
        })
        
        # Filter to ensure only valid symptoms are returned (case-insensitive matching)
        valid_symptoms = []
        for symptom in result.get("symptoms", []):
            # Case-insensitive matching
            for valid_symptom in symptoms:
                if symptom.lower().strip() == valid_symptom.lower().strip():
                    valid_symptoms.append(valid_symptom)
                    break
        
        return {"symptoms": valid_symptoms}
    except Exception as e:
        return {"symptoms": [], "error": str(e)}

# ===========================
# DISEASE PREDICTION FUNCTION
# ===========================
def predict_disease(symptoms_input, top_n=3):
    """
    Predict diseases based on symptoms
    
    Args:
        symptoms_input: List of symptom names
        top_n: Number of top predicted diseases to show
    
    Returns:
        List of top predicted diseases with confidence
    """
    # Check if model is properly loaded
    if not symptoms or not tier2_model or not le:
        print("❌ Model not properly loaded for prediction")
        return []
    
    # Convert input to standard format
    patient = np.zeros(len(symptoms))
    
    for symptom in symptoms_input:
        if symptom in symptoms:
            idx = list(symptoms).index(symptom)
            patient[idx] = 1
    
    # Get probabilities from Tier 2 model
    tier2_proba = tier2_model.predict_proba([patient])[0]
    
    # Get top predictions
    top_indices = np.argsort(tier2_proba)[::-1][:top_n]
    results = []
    
    for idx in top_indices:
        disease = le.classes_[idx]
        confidence = tier2_proba[idx]
        
        # Format disease name
        display_name = category_map.get(disease, disease)
        display_name = display_name.replace('_rare_variant', ' (rare variant)')
        
        # Check if critical
        critical_terms = ['heart attack', 'stroke', 'sepsis', 'meningitis', 'pulmonary embolism', 
                         'cancer', 'tumor', 'acute', 'severe', 'emergency']
        is_critical = any(term in display_name.lower() for term in critical_terms)
        
        results.append({
            "disease": display_name,
            "confidence": float(confidence),
            "is_critical": is_critical
        })
    
    return results

# ===========================
# FLASK ROUTES
# ===========================
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/disclaimer')
def disclaimer():
    return render_template('disclaimer.html')

@app.route('/api/map_symptoms', methods=['POST'])
def api_map_symptoms():
    data = request.json
    user_input = data.get('symptoms', '')
    
    if not user_input:
        return jsonify({"error": "No symptoms provided"}), 400
    
    result = map_symptoms(user_input)
    return jsonify(result)

@app.route('/api/predict', methods=['POST'])
def api_predict():
    data = request.json
    symptoms = data.get('symptoms', [])
    
    if not symptoms:
        return jsonify({"error": "No symptoms provided"}), 400
    
    # Check if model is properly loaded
    if not symptoms or not tier2_model or not le:
        return jsonify({"error": "Model not loaded properly. Prediction unavailable."}), 500
    
    predictions = predict_disease(symptoms)
    return jsonify({"predictions": predictions})

@app.route('/health')
def health_check():
    """Health check endpoint for Render"""
    model_loaded = tier2_model is not None and le is not None and len(symptoms) > 0
    api_key_set = bool(os.getenv("GOOGLE_API_KEY"))
    
    status = {
        "status": "healthy" if model_loaded and api_key_set else "unhealthy",
        "model_loaded": model_loaded,
        "api_key_set": api_key_set,
        "symptom_count": len(symptoms) if symptoms else 0
    }
    
    return jsonify(status), 200 if model_loaded and api_key_set else 503

if __name__ == '__main__':
    # Get port from environment - Render sets this automatically
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    app.run(
        host='0.0.0.0',
        port=port,
        debug=False
    )
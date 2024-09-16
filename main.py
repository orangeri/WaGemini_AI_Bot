import google.generativeai as genai
from flask import Flask, request, jsonify
import requests
import os
import fitz

wa_token = os.environ.get("WA_TOKEN")
genai.configure(api_key=os.environ.get("GEN_API"))
phone_id = os.environ.get("PHONE_ID")
phone = os.environ.get("PHONE_NUMBER")
name = "Avgan"
bot_name = "Arin"
model_name = "gemini-1.5-flash-latest"

app = Flask(__name__)

generation_config = {
    "temperature": 1,
    "top_p": 0.95,
    "top_k": 0,
    "max_output_tokens": 8192,
}

safety_settings = [
    {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
    {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_MEDIUM_AND_ABOVE"},
]

model = genai.GenerativeModel(model_name=model_name,
                              generation_config=generation_config,
                              safety_settings=safety_settings)

convo = model.start_chat(history=[])

convo.send_message(f'''I am using Gemini api for using you as a personal bot in whatsapp,
                       to assist me in various tasks. 
                       So from now you are "{bot_name}" created by {name} ( Yeah it's me, my name is {name}). 
                       And don't give any response to this prompt. 
                       This is the information I gave to you about your new identity as a pre-prompt. 
                       This message always gets executed when i run this bot script. 
                       So reply to only the prompts after this. Remember your new identity is {bot_name}.''')

def send(answer):
    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    headers = {
        'Authorization': f'Bearer {wa_token}',
        'Content-Type': 'application/json'
    }
    data = {
        "messaging_product": "whatsapp",
        "to": f"{phone}",
        "type": "text",
        "text": {"body": f"{answer}"},
    }
    
    response = requests.post(url, headers=headers, json=data)
    return response

def save_file(content, filename):
    permanent_directory = "/path/to/permanent/storage"
    if not os.path.exists(permanent_directory):
        os.makedirs(permanent_directory)
    
    permanent_path = os.path.join(permanent_directory, filename)
    
    with open(permanent_path, "wb") as file:
        file.write(content)
    
    return permanent_path

# Menyimpan konteks gambar yang telah diproses
processed_images = {}

@app.route("/", methods=["GET", "POST"])
def index():
    return "Bot"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        if mode == "subscribe" and token == "BOT":
            return challenge, 200
        else:
            return "Failed", 403
    elif request.method == "POST":
        try:
            data = request.get_json()["entry"][0]["changes"][0]["value"]["messages"][0]
            if data["type"] == "text":
                prompt = data["text"]["body"]
                # Periksa apakah prompt adalah pertanyaan tentang gambar yang sudah diproses
                if prompt.startswith("What about the image with ID"):
                    image_id = prompt.split()[-1]
                    if image_id in processed_images:
                        answer = processed_images[image_id]["description"]
                        send(answer)
                    else:
                        send("I don't have information about that image.")
                else:
                    convo.send_message(prompt)
                    send(convo.last.text)
            else:
                media_url_endpoint = f'https://graph.facebook.com/v18.0/{data[data["type"]]["id"]}/'
                headers = {'Authorization': f'Bearer {wa_token}'}
                media_response = requests.get(media_url_endpoint, headers=headers)
                media_url = media_response.json()["url"]
                media_download_response = requests.get(media_url, headers=headers)
                
                if data["type"] == "audio":
                    filename = "temp_audio.mp3"
                elif data["type"] == "image":
                    filename = "temp_image.jpg"
                elif data["type"] == "document":
                    filename = "temp_document.pdf"
                
                permanent_path = save_file(media_download_response.content, filename)
                
                file = genai.upload_file(path=permanent_path, display_name="tempfile")
                response = model.generate_content(["What is this", file])
                answer = response._result.candidates[0].content.parts[0].text
                
                # Simpan informasi gambar ke dictionary
                processed_images[data["id"]] = {"path": permanent_path, "description": answer}
                
                convo.send_message(f"This is a voice/image message from user transcribed by an llm model, reply to the user based on the transcription: {answer}")
                send(convo.last.text)
        except Exception as e:
            print(e)
            pass
        return jsonify({"status": "ok"}), 200

if __name__ == "__main__":
    app.run(debug=True, port=8000)

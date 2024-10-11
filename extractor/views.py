import os

import openai
from openai import OpenAI
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from spire.doc import Document

from .serializers import DocumentUploadSerializer
from django.conf import settings
from pdfminer.high_level import extract_text as extract_pdf_text
import json

OPENAI_API_KEY = settings.OPENAI_API_KEY
class DocumentUploadView(APIView):
    def post(self, request, format=None):
        serializer = DocumentUploadSerializer(data=request.data)
        if serializer.is_valid():
            file = serializer.validated_data['file']
            # Save the file to media/uploads/
            file_path = os.path.join(settings.MEDIA_ROOT, 'uploads', file.name)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'wb+') as destination:
                for chunk in file.chunks():
                    destination.write(chunk)

            # Extract text from the file
            try:
                if file.name.endswith('.pdf'):
                    text = extract_pdf_text(file_path)
                elif file.name.endswith(('.doc', '.docx')):
                    document = Document()
                    document.LoadFromFile(file_path)
                    text = document.GetText()
                    document.Close()
                else:
                    return Response({"error": "Unsupported file type."}, status=status.HTTP_400_BAD_REQUEST)
            except Exception as e:
                return Response({"error": f"Failed to extract text: {str(e)}"},
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            # Prepare prompt for AI
            prompt = f"""
            Extract the following details from the provided CV:

            Personal Information:
            - Name
            - Gender (assume gener from name if you can)
            - Age

            Education (should be an array of objects):
            - Academic Level (should be in the format of Degree, Major, Minor. e.g., Bachelor, Computer Science, Software Engineering)
            - Institution (e.g., University of Dubai)
            - GPA/Grade (e.g., 3.9 GPA)
            - Start date – End date

            Work Experience (should be an array of objects):
            - Company
            - Location
            - Role
            - Start date – End date
            - Description
            
            Provide the extracted information in JSON format.
            JSON keys should be snake case (small letters lowercase words separated by underscores)
            dates should be in MMM, YYYY format if available. otherwise use what is suitable , but should unified. 
            personal information can be extracted fro linkedIn link if available
            If a field is not found, use "N/A".

            CV Text:
            {text}
            """
            print("text length is: ", len(text))
            print("prompt length is: ", len(prompt))
            try:
                client = OpenAI(
                    # This is the default and can be omitted
                    api_key=OPENAI_API_KEY,
                    organization='org-Rxx8eES4HHUJKkg6saNhJ5A3',
                    project='proj_pMPXpkVedeXTKyO2HfVQjJq0',
                )
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[
                        {"role": "system",
                         "content": "You are a helpful assistant that extracts information from CVs."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0
                )
                extracted_info = response.choices[0].message.content
                try:
                    json_str = extracted_info.split("```json", 1)[1].rsplit("```", 1)[0]
                    extracted_data = json.loads(json_str)
                except IndexError:
                    try:
                        extracted_data = json.loads(extracted_info)
                    except Exception as e:
                        extracted_data = {"error": f"Failed to parse AI response. \n\n {e} \n\n {extracted_info}"}
                        return Response(extracted_data, status=status.HTTP_400_BAD_REQUEST)

                return Response(extracted_data, status=status.HTTP_200_OK)

            except openai.APIConnectionError as e:
                print("The server could not be reached")
                print(e.__cause__)  # an underlying Exception, likely raised within httpx.
                return Response({"error": f"{e}"}, status=status.HTTP_400_BAD_REQUEST)
            except openai.RateLimitError as e:
                print("A 429 status code was received; we should back off a bit.")
                return Response({"error": f"{e}"}, status=e.status_code)
            except openai.APIStatusError as e:
                return Response({"error": f"{e}"}, status=e.status_code)

        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

from django.shortcuts import render
from django.http import FileResponse, HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
import os
import uuid
import json
import yt_dlp
import tempfile
import shutil
from django.views import View
from .models import Item


def get_items(request):
    """Get all items from database"""
    if request.method == "GET":
        items = Item.objects.all()
        items_data = []
        
        for item in items:
            item_data = {
                "id": item.id,
                "name": item.name,
                "description": item.description,
                "price": float(item.price) if item.price else None,
                "image_url": request.build_absolute_uri(item.image.url) if item.image else None,
                "created_at": item.created_at.isoformat() if hasattr(item, 'created_at') else None
            }
            items_data.append(item_data)
        
        return JsonResponse({"items": items_data}, status=200)
    else:
        return JsonResponse({"error": "Invalid request method"}, status=405)
    
class HomeView(View):
    def get(self, request):
        items = Item.objects.all()
        return render(request, "base/home.html", {"items": items})


@csrf_exempt
def add_item(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            name = data.get("name")
            description = data.get("description")
            price = data.get("price")
            image = data.get("image")
            if not name or not description:
                return JsonResponse(
                    {"error": "Name and description are required"}, status=400
                )
            item = Item.objects.create(
                name=name, description=description, image=image, price=price
            )
            return JsonResponse(
                {"id": item.id, "name": item.name, "description": item.description},
                status=201,
            )
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)
    else:
        return HttpResponse("Invalid request method", status=405)


@csrf_exempt
def download_video(request):
    if request.method == "POST":
        try:
            # Parse JSON data from request body
            data = json.loads(request.body)
            url = data.get("url")
            format_type = data.get("format")
        except json.JSONDecodeError:
            return JsonResponse({"error": "Invalid JSON"}, status=400)

        if not url:
            return JsonResponse({"error": "No URL provided"}, status=400)

        if format_type not in ["mp3", "mp4"]:
            return JsonResponse(
                {"error": "Invalid format. Only mp3 and mp4 are supported"}, status=400
            )

        # Generate a unique filename without extension
        unique_filename = str(uuid.uuid4())
        output_template = os.path.join(settings.BASE_DIR, unique_filename + ".%(ext)s")

        # Configure download options based on format
        if format_type == "mp3":
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": output_template,
                "noplaylist": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
        elif format_type == "mp4":
            ydl_opts = {
                "format": "best[ext=mp4]/best",
                "outtmpl": output_template,
                "noplaylist": True,
            }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])

            # Find the downloaded file (since extension might vary)
            import glob

            pattern = os.path.join(settings.BASE_DIR, unique_filename + ".*")
            downloaded_files = glob.glob(pattern)

            if downloaded_files:
                actual_filename = downloaded_files[0]  # Take the first match
                download_filename = os.path.basename(actual_filename)

                # Move file to temp directory - OS will clean it up
                temp_dir = tempfile.mkdtemp()
                temp_file = os.path.join(temp_dir, download_filename)
                shutil.move(actual_filename, temp_file)

                response = FileResponse(
                    open(temp_file, "rb"),
                    as_attachment=True,
                    filename=download_filename,
                )
                return response
            else:
                return JsonResponse(
                    {"error": "File not found after download"}, status=500
                )

        except Exception as e:
            # Clean up any files that might have been created
            try:
                # Try to remove files matching the pattern
                import glob

                pattern = os.path.join(settings.BASE_DIR, unique_filename + ".*")
                for file_path in glob.glob(pattern):
                    os.remove(file_path)
            except:
                pass
            return JsonResponse(
                {"error": f"Error downloading video: {str(e)}"}, status=500
            )

    else:
        return HttpResponse("Invalid request method", status=405)


import os 
import shutil
from datetime import datetime




Target_Folder = "" 

# File type groups 

File_Types = {"Images": [".jpg", ".jpeg", ".png", ".gif"], "PDF": [".pdf"], "PowerPoint": [".pwp"], 
            "Docs": [".docx", ".doc", ".txt"], "Videos": [".mp4", ".mov"], "Others": [] }


def get_category(extension):
    for category, exts in File_Types.items():
        if extension in exts:
            return category
    return "Others"

def main():
    
    counter = {}
    for file in os.listdir(Target_Folder):
        
        file_path = os.path.join(Target_Folder, file)
        
        
        # Skip folders 
        if os.path.isdir(file_path):
            continue 
        # Get file extension 
        name, ext = os.path.splitext(file)
        ext = ext.lower() 
        
        # Get creation time get year 
        timestamp = os.path.getctime(file_path)
        year = datetime.fromtimestamp(timestamp).year 
        
        # Get category 
        category = get_category(ext)
        
        # Create folder path 
        year_folder = os.path.join(Target_Folder, str(year))
        category_folder = os.path.join(year_folder, category)
        
        os.makedirs(category_folder, exist_ok=True)
        
        
        # Counter Key 
        key = (year, category, ext) 
        
        if key not in counters: 
            counters[key] = 1 
            
        number = counters[key]
        
        # New filename 
        new_name = f"{year}_{category}_{number:03d}{ext}"
        new_path = os.path.join(category_folder, new_name)
        
        counters[key] += 1
        
        shutil.move(file_path, new_path)
        
        print(f"Moved: {file} -> {new_name}")
        
if __name__ == "__main__":
    main()


        
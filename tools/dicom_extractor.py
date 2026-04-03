import pydicom
import csv
import os

folder = r"D:\Slicer_External_Data\DICOM2\Heart_CT"
output_file = 'dicom_metadata.csv'

with open(output_file, 'w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['FileName', 'PatientID', 'StudyDate', 'SliceThickness', 'Rows', 'Columns'])
    
    count = 0
    for file in os.listdir(folder):
        file_path = os.path.join(folder, file)
        
        # 跳过文件夹，只处理文件
        if not os.path.isfile(file_path):
            continue
            
        try:
            ds = pydicom.dcmread(file_path)
            writer.writerow([
                file,
                ds.PatientID,
                ds.StudyDate,
                ds.SliceThickness if 'SliceThickness' in ds else 'N/A',
                ds.Rows,
                ds.Columns
            ])
            count += 1
        except:
            continue  # 不是DICOM文件就跳过
    
    print(f"✅ 已处理{count}个文件")

import pydicom
from pydicom.uid import generate_uid


uid = generate_uid() # Use default dicom root 1.2.826.0.1.3680043.8.498

print("Generated UID:", uid)


my_root = "1.2.840.123467" # Use you assigned DICOM root from NEMA
custom_uid = generate_uid(prefix=my_root + '.')
print('Custom UID:', custom_uid)

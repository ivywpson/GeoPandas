import os
import geopandas as gpd
from shapely.geometry import Polygon
from datetime import *

def Rec(root, allFiles=[], isShow = False):
    list = os.listdir(root)
    #list2 = str(list).encode("utf-8").decode('unicode_escape')
    #print(list2)
    for name in list:
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            if name[-3:] == "shp" and not name[-11:-4] == "Fishnet":
                allFiles.append(path)
        else:
            Rec(path, allFiles, False)
    if isShow:
        print('\n'.join(allFiles))
    return allFiles #这里面包括了所有需要遍历的shp的路径

fileList = Rec("D:\北大\挑战杯\全国62个城市模型") #此处路径修改为城市模型根目录
print(fileList)
for file in fileList:
    data = gpd.read_file(file)
    data = data.to_crs(3857)
    file2 = file.replace(".shp", "Web.shp")
    data.to_file(file2, driver='ESRI Shapefile',encoding='utf-8')
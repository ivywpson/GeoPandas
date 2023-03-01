# This is a sample Python script.
import os
import geopandas as gpd
# import matplotlib.pyplot as plt
import rasterio as ro
from shapely.geometry import Polygon
from datetime import *

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.

'''
nantong,changzhou这两个的处理速度和数据量不成正比，发现是检查有没有建筑那一步很慢
进一步说，所有拼音命名的shp速度和数据量都不太成正比（例如baoding），不知是否是shp的问题
shp大小上没有明显异常。是因为存储了太多碎屑多边形吗？
'''

def Rec(root, allFiles=[], isShow = False):
    list = os.listdir(root)
    #list2 = str(list).encode("utf-8").decode('unicode_escape')
    #print(list2)
    for name in list:
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            if name[-7:] == "Web.shp" and not name[-11:-4] == "Fishnet":
                allFiles.append(path)
        else:
            Rec(path, allFiles, False)
    if isShow:
        print('\n'.join(allFiles))
    return allFiles #这里面包括了所有需要遍历的shp的路径

# bbox是一个元组，格式为（左下经，左下纬，右上经，右上纬）
'''
参数说明：
path：shp路径
bbox：待读取区域的最小外包矩形
返回值说明：
blockArea：由于原始栅格是大地坐标系，在投影坐标系中的面积大小不确定，需要再计算一遍
Boolean：该处若有建筑且有人口则为真，否则为假
shp：返回裁剪后的shp
'''
def readShp(path, bbox):
    poly = createPolygon(bbox)
    print(poly)
    data = gpd.read_file(path, bbox)
    print("Data read")
    '''
    原本用的办法是读取整个城市的shp，每次根据bbox裁剪，判断建筑面积之和是否为0，为0则舍去
    实践发现效率非常低，三亚需要半小时才能处理完，主要是裁剪这步很慢，判断面积之和这步也会消耗时间
    现在用的方法是先根据bbox读取局部shp，判断gpd是否为空，不为空再裁剪
    效率提升了不少，三亚十分钟可以处理完，说明根据bbox读取的IO效率远比裁剪要高
    bbox读取只用获取和边界相交的多边形，裁剪还要对多边形修修补补，修修补补使得算法速度很慢
    2023.3.1
    RuntimeWarning: Sequential read of iterator was interrupted. Resetting iterator. This can negatively impact the performance.
    for feature in features_lst:
    极大地影响了运行效率，上海跑了一夜都没跑完
    '''
    if data.empty:
        return True, data, 0
    data_clip = gpd.clip(gdf=data, mask=poly)  # 参见https://geopandas.org/en/stable/gallery/plot_clip.html
    print("Data_clip read")
    # data_clip = data_clip.to_crs(3857)  # 转为投影坐标系
    if data_clip.empty:
        return True, data_clip, 0
    # fileName = str(bbox) + ".shp"
    # data_clip.to_file(fileName)
    # poly = poly.to_crs(3857)
    poly["area"] = poly.area
    blockArea = poly["area"].sum()
    return False, data_clip, blockArea

'''
参数说明：
path：tif的路径
返回值说明：
b：转化为ndarray的tif图像，可以用numpy的方法操作。是一个三维数组，每个维度分别是波段，横坐标，纵坐标（左下角开始）
bbox：栅格的最小外包矩形，格式为（左下经，左下纬，右上经，右上纬）
'''
def readTif(path):
    data = ro.open(path)
    bbox = data.bounds
    b = data.read()  # read函数将栅格图像转换为numpy.ndarray，之后可以用numpy方法操作了
    return b, bbox

'''
参数说明：
bbox：用于创建多边形的最小外包矩形坐标
返回值说明：
poly_gdf：返回存储在geodataframe中的多边形
'''
def createPolygon(bbox):
    polygon = Polygon([(bbox[0], bbox[1]), (bbox[0], bbox[3]),
                       (bbox[2], bbox[3]), (bbox[2], bbox[1]), (bbox[0], bbox[1])])
    poly_gdf = gpd.GeoDataFrame([1], geometry=[polygon], crs=3857)
    return poly_gdf

'''
参数说明：
raster：用于获取人口数据的栅格，应当是ndarray
res：进一步划分栅格的分辨率，原始分辨率为0.01，假设对应1000m
shp_bbox：当前shp的最小外包矩形
tif_bbox：当前栅格的最小外包矩形，格式都是（左下经，左下纬，右上经，右上纬）
返回值说明：
pop：人口数量
'''
def getPop(raster, res, shp_bbox, tif_bbox): # 现在157行的程序使用的仍然是度分秒形式的bbox，需要转换为投影坐标
    size = 500 // res
    grid_col = int(((tif_bbox[0] - shp_bbox[0]) // res) // size) # 如果tif换成投影坐标系，这行得改
    grid_row = int(((tif_bbox[3] - shp_bbox[3]) // res) // size)
    pop = raster[0][grid_row][grid_col] // (size ** 2)
    # print(pop)
    return pop

def process(fileList, res):
    Note = open("D:\\FileSave\\log.txt", mode='w')
    Note.write("Resolution: " + str(res) + "m\n")
    for files in fileList: # fileList是所有待处理的文件路径构成的列表
        blank = gpd.GeoDataFrame(
            {
                "blockArea": [],
                "floorSum": [],
                "groundSum": [],
                "Pop": [],
                "DensityB": [],
                "DensityF": [],
                "DensityG": [],
            }
        )
        file_shp = files # Web Mercator投影的建筑shp
        file_tif = files.replace("Web.shp", "Web2.tif") # Web Mercator坐标的人口栅格，已裁剪
        basename = os.path.basename(files)
        filename = basename.replace("Web.shp", "")
        # data_gpd = gpd.read_file(file_shp)
        tif, bbox_temp = readTif(file_tif)  # tif是array格式的人口栅格，bbox是栅格的最小外包矩形
        # a, b, c, d = round(bbox_temp[0], 4), round(bbox_temp[1], 4), round(bbox_temp[2], 4), round(bbox_temp[3], 4)
        # tif的bbox不取整会出现118.40000000005这种东西，影响后续计算
        # WGS84时代的程序
        a, b, c, d = bbox_temp[0], bbox_temp[1], bbox_temp[2], bbox_temp[3] # Web Mercator时代的程序
        bbox = (a, b, c, d) # tif的bbox，以tuple存储
        totalgrid = int(((c-a)/res)*((d-b)/res)) # 格网数量
        # print(bbox)
        print("============================================")
        print("Processing city: {}".format(filename))
        print("Total number of grids: {}".format(totalgrid))
        print("Start at: {}".format(datetime.now()))
        print("============================================")
        Note.write("============================================\n")
        Note.write("Processing city: " + filename + "\n")
        Note.write("Total number of grids: " + str(totalgrid) + "\n")
        Note.write("Bounding box: " + str(bbox) + "\n")
        Note.write("Start at: " + str(datetime.now()) + "\n")
        Note.write("============================================\n")
        left, bottom = a, b
        # right, top = round(a+res, 4), round(b+res, 4)  # 不取整会出现浮点数错误，例如1+0.5=1.49999999
        # WGS84时代的程序
        right, top = a + res, b + res
        grid_num = 1
        while bottom < bbox[3]:
            while left < bbox[2]:
                if(grid_num == "192"):
                    pass
                print(grid_num)
                Note.write("Grid number: " + str(grid_num) + "\n")
                grid_num += 1
                shp_bbox = (left, bottom, right, top)
                # print(shp_bbox)
                Note.write("Grid bbox: " + str(shp_bbox) + "\n")
                popu = getPop(tif, res, shp_bbox, bbox)
                if popu != 0:  # 栅格人口不为0
                    noBuild, shp, blockArea = readShp(file_shp, shp_bbox)  # 取出该栅格范围对应的建筑轮廓
                    # print(shp)

                    if noBuild:  # 没有建筑
                        print("No building. Pass.")
                        Note.write("No building. Pass.\n")
                        # left, right = round(left + res, 4), round(right + res, 4)
                        # WGS84时代的程序
                        left, right = left + res, right + res
                        continue
                    # 有建筑
                    shp["area"] = shp.area   # 计算面积
                    shp["area_floor"] = shp["area"] * shp["Floor"]
                    shp["area_ground"] = shp["area"] * (shp["Floor"] - 1)
                    floorSum = shp["area_floor"].sum()   # 仅考虑楼高的区域面积
                    groundSum = shp["area_ground"].sum() + blockArea   # 考虑楼高和渔网底面面积
                    blank = blank.append(
                        {
                            "blockArea": blockArea,  # 面积以平方米计
                            "floorSum": floorSum,
                            "groundSum": groundSum,
                            "Pop": popu,
                            "DensityB": popu * 1000000 / blockArea,  # 密度以人/平方千米计
                            "DensityF": popu * 1000000 / floorSum,
                            "DensityG": popu * 1000000 / groundSum,
                        },
                        ignore_index=True
                    )
                    # Can only append a Series if ignore_index=True or if the Series has a name
                    # left, right = round(left+res, 4), round(right+res, 4)  # 栅格向右移动一格
                    # WGS84时代的程序
                    left, right = left + res, right + res
                    print("Successfully appended.")
                    Note.write("Successfully appended.\n")
                else:  # 栅格人口为0
                    print("No people. Pass.")
                    Note.write("No people. Pass.\n")
                    # left, right = round(left + res, 4), round(right + res, 4)
                    # WGS84时代的程序
                    left, right = left + res, right + res
            # left, right = round(bbox[0], 4), round(bbox[0]+res, 4),  # 栅格回到本行最左侧
            # WGS84时代的程序
            left, right = bbox[0], bbox[0] + res
            # bottom, top = round(bottom+res, 4), round(top+res, 4)  # 栅格向上移动一格
            # WGS84时代的程序
            bottom, top = bottom + res, top + res
        csvname = "D:\\FileSave\\" + filename + str(res) + "m.csv"
        blank.to_csv(csvname)
    Note.close()

# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    fileList = Rec("D:\北大\挑战杯\全国62个城市模型")
    fileList[23:] = []  # 33项（从0项计）及之后置为空
    fileList[:1] = []  # 从list中裁剪出要用的路径
    print('\n'.join(fileList))
    process(fileList, 500)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/

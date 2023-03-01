import numpy as np
import rasterio
from rasterio.warp import calculate_default_transform, reproject, Resampling
import os

# 对于[文件名].tif，projection函数会生成[文件名]Web.tif，为投影至Web Mercator的栅格图像
# 对于[文件名]Web.tif，resampling函数会生成[文件名]Web2.tif，为栅格大小调整至500m x 500m的栅格图像
# 前提条件：每个城市文件夹中都有已经裁剪好的tif文件，例如“杭州建筑轮廓数据”文件夹内有“杭州.tif”

def projection(path):

    path_Web = path.replace(".tif", "Web.tif")
    dst_crs = 'EPSG:3857' # Web Mercator

    with rasterio.open(path) as src:
        transform, width, height = calculate_default_transform(
            src.crs, dst_crs, src.width, src.height, *src.bounds)
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': dst_crs,
            'transform': transform,
            'width': width,
            'height': height
        })

        with rasterio.open(path_Web, 'w', **kwargs) as dst:
            for i in range(1, src.count + 1):
                reproject(
                    source=rasterio.band(src, i),
                    destination=rasterio.band(dst, i),
                    src_transform=src.transform,
                    src_crs=src.crs,
                    dst_transform=transform,
                    dst_crs=dst_crs,
                    resampling=Resampling.nearest)

def resampling(res, path):
    path = path.replace(".tif", "Web.tif")
    path2 = path.replace("Web", "Web2")

    with rasterio.open(path) as dataset:
        # resample data to target shape using upscale_factor
        pxsz, pysz = dataset.res
        upscale_factor = pxsz / res
        # print(dataset.height * upscale_factor, dataset.width * upscale_factor)
        data = dataset.read(
            out_shape=(
                dataset.count,
                int(dataset.height * upscale_factor),
                int(dataset.width * upscale_factor)
            ),
            resampling=Resampling.bilinear
        )

        # print('Shape before resample:', dataset.shape)
        # print('Shape after resample:', data.shape[1:])

        # scale image transform
        dst_transform = dataset.transform * dataset.transform.scale(
            (1 / upscale_factor),
            (1 / upscale_factor)
        )

        # print('Transform before resample:\n', dataset.transform, '\n')
        # print('Transform after resample:\n', dst_transform)

        # Write outputs
        # set properties for output
        dst_kwargs = dataset.meta.copy()
        dst_kwargs.update(
            {
                "transform": dst_transform,
                "width": data.shape[-1],
                "height": data.shape[-2],
            }
        )

        with rasterio.open(path2, "w", **dst_kwargs) as dst:
            # iterate through bands
            for i in range(data.shape[0]):
                  dst.write(data[i].astype(rasterio.float32), i+1)

def Rec(root, allFiles=[], isShow = False):
    list = os.listdir(root)
    #list2 = str(list).encode("utf-8").decode('unicode_escape')
    #print(list2)
    for name in list:
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            if name[-3:] == "tif" and not name[-7:-4] == "Web" and not name[-8:-4] == "Web2":
                allFiles.append(path)
        else:
            Rec(path, allFiles, False)
    if isShow:
        print('\n'.join(allFiles))
    return allFiles #这里面包括了所有需要遍历的shp的路径

fileList = Rec("D:\北大\挑战杯\全国62个城市模型") #此处路径修改为城市模型根目录
fileList[33:] = []
print(fileList)
for file in fileList:
    projection(file)
    resampling(500.0, file)
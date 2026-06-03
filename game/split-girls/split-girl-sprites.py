#!/usr/bin/env python3
"""
分割女孩精灵图 - 将 sprite sheet 切割成单独的角色图像
输出:
1. 带红色切割线的原图
2. 按坐标命名的切割后图像
3. 切割线坐标保存为 mat 文件
"""

import numpy as np
from PIL import Image, ImageDraw
import os
from scipy import io
from scipy.ndimage import label

def load_image(path):
    """加载图片并转换为 numpy 数组"""
    img = Image.open(path)
    return img, np.array(img)

def find_character_boxes(arr):
    """
    找到所有完整角色的边界框
    只提取高度足够大的完整角色（排除文字和装备小图标）
    """
    # 转换为灰度并二值化
    gray = np.mean(arr[:, :, :3], axis=2)  # 忽略 alpha
    # 非白色像素（阈值设为 240）
    mask = gray < 240

    # 查找所有连通区域
    labeled, num_features = label(mask)

    boxes = []
    for i in range(1, num_features + 1):
        coords = np.where(labeled == i)
        y_min, y_max = coords[0].min(), coords[0].max()
        x_min, x_max = coords[1].min(), coords[1].max()

        height = y_max - y_min
        width = x_max - x_min

        # 过滤条件：
        # 1. 高度至少 100 像素（排除小图标和文字）
        # 2. y 范围在 50-600 之间（排除顶部的文字和底部的装备）
        if height >= 100 and y_min >= 50 and y_max <= 600:
            boxes.append((x_min, y_min, x_max, y_max))

    return boxes

def merge_nearby_boxes(boxes, x_threshold=20, y_threshold=20):
    """合并水平和垂直方向都很接近的边界框"""
    if not boxes:
        return []

    merged = []
    used = [False] * len(boxes)

    for i, box1 in enumerate(boxes):
        if used[i]:
            continue

        current = box1
        used[i] = True

        # 尝试合并其他框
        changed = True
        while changed:
            changed = False
            for j, box2 in enumerate(boxes):
                if used[j]:
                    continue

                x1, y1, x2, y2 = current
                x1b, y1b, x2b, y2b = box2

                # 检查是否重叠或接近
                x_overlap = not (x2 + x_threshold < x1b or x2b + x_threshold < x1)
                y_overlap = not (y2 + y_threshold < y1b or y2b + y_threshold < y1)

                if x_overlap and y_overlap:
                    # 合并
                    current = (
                        min(x1, x1b),
                        min(y1, y1b),
                        max(x2, x2b),
                        max(y2, y2b)
                    )
                    used[j] = True
                    changed = True

        merged.append(current)

    # 按位置排序：先按行（y），再按列（x）
    merged.sort(key=lambda b: (b[1] // 50 * 50, b[0]))

    return merged

def draw_cutting_lines(img, all_boxes, output_path):
    """在图片上绘制红色切割线"""
    img_copy = img.copy()
    draw = ImageDraw.Draw(img_copy)

    # 收集所有唯一的 x 和 y 切割线
    x_lines = set()
    y_lines = set()
    margin = 5

    for x1, y1, x2, y2 in all_boxes:
        x_lines.add(x1 - margin)
        x_lines.add(x2 + margin)
        y_lines.add(y1 - margin)
        y_lines.add(y2 + margin)

    # 绘制垂直切割线（红色）
    for x in sorted(x_lines):
        draw.line([(x, 0), (x, img.height)], fill='red', width=1)

    # 绘制水平切割线（红色）
    for y in sorted(y_lines):
        draw.line([(0, y), (img.width, y)], fill='red', width=1)

    img_copy.save(output_path)
    print(f"已保存带切割线的图片：{output_path}")

    return sorted(x_lines), sorted(y_lines)

def save_characters(img, all_boxes, output_dir):
    """保存切割后的角色图像"""
    os.makedirs(output_dir, exist_ok=True)

    # 先清理旧的 char_*.png 文件
    for f in os.listdir(output_dir):
        if f.startswith('char_') and f.endswith('.png'):
            os.remove(os.path.join(output_dir, f))
            print(f"清理旧文件：{f}")

    saved_files = []
    margin = 5

    for i, (x1, y1, x2, y2) in enumerate(all_boxes):
        crop_box = (x1 - margin, y1 - margin, x2 + margin, y2 + margin)
        cropped = img.crop(crop_box)
        filename = f"char_{i:02d}_{x1-margin}x{y1-margin}_{x2+margin}x{y2+margin}.png"
        filepath = os.path.join(output_dir, filename)
        cropped.save(filepath)
        saved_files.append({
            'filename': filename,
            'filepath': filepath,
            'x1': x1 - margin,
            'y1': y1 - margin,
            'x2': x2 + margin,
            'y2': y2 + margin
        })
        print(f"已保存：{filename}")

    return saved_files

def save_coordinates_mat(all_boxes, output_path):
    """保存切割线坐标为 mat 文件"""
    margin = 5

    x_set = set()
    y_set = set()

    for x1, y1, x2, y2 in all_boxes:
        x_set.add(float(x1 - margin))
        x_set.add(float(x2 + margin))
        y_set.add(float(y1 - margin))
        y_set.add(float(y2 + margin))

    cutting_lines = {
        'x': np.array(sorted(x_set), dtype=np.float64),
        'y': np.array(sorted(y_set), dtype=np.float64)
    }

    io.savemat(output_path, cutting_lines)
    print(f"已保存切割线坐标：{output_path}")
    print(f"  X 切割线 ({len(cutting_lines['x'])} 条): {cutting_lines['x']}")
    print(f"  Y 切割线 ({len(cutting_lines['y'])} 条): {cutting_lines['y']}")

def main():
    # 输入输出路径
    input_path = 'assets/timeline.girl.png'
    output_dir = 'assets/split-girls'

    print(f"加载图片：{input_path}")
    img, arr = load_image(input_path)
    print(f"图片尺寸：{img.size}")

    # 找到所有角色边界框
    boxes = find_character_boxes(arr)
    print(f"找到 {len(boxes)} 个候选角色区域")

    # 合并接近的框
    merged_boxes = merge_nearby_boxes(boxes)
    print(f"合并后：{len(merged_boxes)} 个完整角色")

    # 打印角色信息
    print("\n角色列表:")
    for i, (x1, y1, x2, y2) in enumerate(merged_boxes):
        print(f"  {i}: ({x1}, {y1}) - ({x2}, {y2})  尺寸：{x2-x1}x{y2-y1}")

    # 输出 1: 带红色切割线的图片
    cutting_img_path = os.path.join(output_dir, 'cutting_lines.png')
    x_lines, y_lines = draw_cutting_lines(img, merged_boxes, cutting_img_path)

    # 输出 2: 切割后的图像
    saved_files = save_characters(img, merged_boxes, output_dir)

    # 输出 3: 保存切割线坐标为 mat 文件
    mat_path = os.path.join(output_dir, 'cutting_coordinates.mat')
    save_coordinates_mat(merged_boxes, mat_path)

    print(f"\n完成！输出目录：{output_dir}")
    print(f"  - 带切割线图片：cutting_lines.png")
    print(f"  - 角色图像：{len(saved_files)} 个")
    print(f"  - 坐标文件：cutting_coordinates.mat")

if __name__ == '__main__':
    main()

/**
 * Tag Resolver 統一模組
 *
 * 將 tagId 解析為 tag 名稱和 category 資訊的共用模組。
 * 供 FilterEngine、SearchEngine、BookDataExporter、Overview Page 等消費端使用。
 *
 * 需求來源: 0.17.2-W2-003
 */

const TAG_RESOLVER_DEFAULTS = {
  FALLBACK_CATEGORY_NAME: '未分類',
  FALLBACK_CATEGORY_COLOR: '#808080',
};

/**
 * 建立 Tag Resolver 實例
 *
 * @param {Object} deps - 依賴注入
 * @param {Function} deps.getTagById - (tagId: string) => Tag | null
 * @param {Function} deps.getCategoryById - (categoryId: string) => TagCategory | null
 * @returns {{ resolveTag: Function, resolveTagsForDisplay: Function, resolveTagName: Function }}
 */
function createTagResolver(deps) {
  if (!deps || typeof deps !== 'object') {
    throw new TypeError('createTagResolver requires deps object');
  }
  if (typeof deps.getTagById !== 'function') {
    throw new TypeError('deps.getTagById must be a function');
  }
  if (typeof deps.getCategoryById !== 'function') {
    throw new TypeError('deps.getCategoryById must be a function');
  }

  const { getTagById, getCategoryById } = deps;

  /**
   * 解析單一 tagId 為完整 tag + category 資訊
   *
   * @param {string} tagId
   * @returns {{ tagId: string, tagName: string, categoryId: string, categoryName: string, categoryColor: string } | null}
   */
  function resolveTag(tagId) {
    if (typeof tagId !== 'string' || tagId === '') {
      return null;
    }

    const tag = getTagById(tagId);
    if (!tag) {
      return null;
    }

    const category = getCategoryById(tag.categoryId);
    const categoryName = category
      ? category.name
      : TAG_RESOLVER_DEFAULTS.FALLBACK_CATEGORY_NAME;
    const categoryColor = category
      ? category.color
      : TAG_RESOLVER_DEFAULTS.FALLBACK_CATEGORY_COLOR;

    return {
      tagId: tag.id,
      tagName: tag.name,
      categoryId: tag.categoryId,
      categoryName,
      categoryColor,
    };
  }

  /**
   * 批量解析 tagIds 為顯示用資料陣列
   *
   * @param {string[]} tagIds
   * @returns {Array<{ tagId: string, tagName: string, categoryId: string, categoryName: string, categoryColor: string }>}
   */
  function resolveTagsForDisplay(tagIds) {
    if (!Array.isArray(tagIds)) {
      return [];
    }

    const results = [];
    for (const tagId of tagIds) {
      if (typeof tagId !== 'string') {
        continue;
      }
      const resolved = resolveTag(tagId);
      if (resolved) {
        results.push(resolved);
      }
    }
    return results;
  }

  /**
   * 便捷方法：單一 tagId → tag 名稱字串
   *
   * @param {string} tagId
   * @returns {string | null}
   */
  function resolveTagName(tagId) {
    if (typeof tagId !== 'string' || tagId === '') {
      return null;
    }

    const tag = getTagById(tagId);
    return tag ? tag.name : null;
  }

  return {
    resolveTag,
    resolveTagsForDisplay,
    resolveTagName,
  };
}

module.exports = { createTagResolver, TAG_RESOLVER_DEFAULTS };

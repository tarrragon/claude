/**
 * Tag Resolver 統一模組 - 單元測試
 *
 * 需求來源: 0.17.2-W2-003
 */

const {
  createTagResolver,
  TAG_RESOLVER_DEFAULTS,
} = require('../../../../src/ui/search/tag-resolver');

// -- 測試用 fixture --

const TAG_SCIFI = {
  id: 'tag-01',
  name: '科幻',
  categoryId: 'cat-01',
  isSystem: false,
};

const TAG_FANTASY = {
  id: 'tag-02',
  name: '奇幻',
  categoryId: 'cat-01',
  isSystem: false,
};

const TAG_ORPHAN = {
  id: 'tag-orphan',
  name: '孤兒標籤',
  categoryId: 'cat-deleted',
  isSystem: false,
};

const CATEGORY_GENRE = {
  id: 'cat-01',
  name: '類別',
  color: '#FF5733',
  isSystem: false,
};

function buildDeps(tagMap, categoryMap) {
  return {
    getTagById: (id) => tagMap.get(id) || null,
    getCategoryById: (id) => categoryMap.get(id) || null,
  };
}

function buildDefaultResolver() {
  const tagMap = new Map([
    [TAG_SCIFI.id, TAG_SCIFI],
    [TAG_FANTASY.id, TAG_FANTASY],
    [TAG_ORPHAN.id, TAG_ORPHAN],
  ]);
  const categoryMap = new Map([[CATEGORY_GENRE.id, CATEGORY_GENRE]]);
  return createTagResolver(buildDeps(tagMap, categoryMap));
}

// -- 測試案例 --

describe('createTagResolver', () => {
  describe('工廠函式驗證', () => {
    it('缺少 deps 參數時拋出 TypeError', () => {
      expect(() => createTagResolver()).toThrow(TypeError);
      expect(() => createTagResolver()).toThrow(
        'createTagResolver requires deps object'
      );
    });

    it('deps 為 null 時拋出 TypeError', () => {
      expect(() => createTagResolver(null)).toThrow(TypeError);
      expect(() => createTagResolver(null)).toThrow(
        'createTagResolver requires deps object'
      );
    });

    it('deps.getTagById 不是函式時拋出 TypeError', () => {
      expect(() =>
        createTagResolver({ getTagById: 'not-fn', getCategoryById: () => {} })
      ).toThrow('deps.getTagById must be a function');
    });

    it('deps.getCategoryById 不是函式時拋出 TypeError', () => {
      expect(() =>
        createTagResolver({ getTagById: () => {}, getCategoryById: 123 })
      ).toThrow('deps.getCategoryById must be a function');
    });

    it('正確依賴時回傳 resolver 物件', () => {
      const resolver = buildDefaultResolver();
      expect(typeof resolver.resolveTag).toBe('function');
      expect(typeof resolver.resolveTagsForDisplay).toBe('function');
      expect(typeof resolver.resolveTagName).toBe('function');
    });
  });

  describe('resolveTag', () => {
    it('正常解析含完整 category 資訊', () => {
      const resolver = buildDefaultResolver();
      const result = resolver.resolveTag('tag-01');

      expect(result).toEqual({
        tagId: 'tag-01',
        tagName: '科幻',
        categoryId: 'cat-01',
        categoryName: '類別',
        categoryColor: '#FF5733',
      });
    });

    it('tag 已刪除時回傳 null', () => {
      const resolver = buildDefaultResolver();
      expect(resolver.resolveTag('tag-deleted')).toBeNull();
    });

    it('category 已刪除時使用 fallback 值', () => {
      const resolver = buildDefaultResolver();
      const result = resolver.resolveTag('tag-orphan');

      expect(result).toEqual({
        tagId: 'tag-orphan',
        tagName: '孤兒標籤',
        categoryId: 'cat-deleted',
        categoryName: TAG_RESOLVER_DEFAULTS.FALLBACK_CATEGORY_NAME,
        categoryColor: TAG_RESOLVER_DEFAULTS.FALLBACK_CATEGORY_COLOR,
      });
    });

    it('空字串 tagId 回傳 null', () => {
      const resolver = buildDefaultResolver();
      expect(resolver.resolveTag('')).toBeNull();
    });
  });

  describe('resolveTagsForDisplay', () => {
    it('批量解析正確，順序與輸入一致', () => {
      const resolver = buildDefaultResolver();
      const results = resolver.resolveTagsForDisplay(['tag-02', 'tag-01']);

      expect(results).toHaveLength(2);
      expect(results[0].tagName).toBe('奇幻');
      expect(results[1].tagName).toBe('科幻');
    });

    it('過濾已刪除 tag', () => {
      const resolver = buildDefaultResolver();
      const results = resolver.resolveTagsForDisplay([
        'tag-01',
        'tag-deleted',
        'tag-02',
      ]);

      expect(results).toHaveLength(2);
      expect(results[0].tagId).toBe('tag-01');
      expect(results[1].tagId).toBe('tag-02');
    });

    it('null 輸入回傳空陣列', () => {
      const resolver = buildDefaultResolver();
      expect(resolver.resolveTagsForDisplay(null)).toEqual([]);
    });

    it('undefined 輸入回傳空陣列', () => {
      const resolver = buildDefaultResolver();
      expect(resolver.resolveTagsForDisplay(undefined)).toEqual([]);
    });

    it('空陣列回傳空陣列', () => {
      const resolver = buildDefaultResolver();
      expect(resolver.resolveTagsForDisplay([])).toEqual([]);
    });

    it('忽略非字串元素', () => {
      const resolver = buildDefaultResolver();
      const results = resolver.resolveTagsForDisplay([
        'tag-01',
        123,
        null,
        'tag-02',
      ]);

      expect(results).toHaveLength(2);
      expect(results[0].tagId).toBe('tag-01');
      expect(results[1].tagId).toBe('tag-02');
    });
  });

  describe('resolveTagName', () => {
    it('正常回傳 tag 名稱字串', () => {
      const resolver = buildDefaultResolver();
      expect(resolver.resolveTagName('tag-01')).toBe('科幻');
    });

    it('tag 不存在時回傳 null', () => {
      const resolver = buildDefaultResolver();
      expect(resolver.resolveTagName('tag-gone')).toBeNull();
    });
  });
});

---
id: test-fenced-edges
---

# EDGE-1 空 fenced block

```
```

# EDGE-2 帶 language hint

```python
Phase 5 再決定 cache
```

# EDGE-3 Tilde fence

~~~
Phase 5 再決定 cache
~~~

# EDGE-4 4-backtick 外層，內部 3-backtick 不閉合

````
Phase 5 再決定 outer
```
還在區塊內 之後再決定
```
````

# EDGE-6 起始 backtick 但結束 tilde（不閉合，視為內容）

```
Phase 5 再決定 mixed
~~~
仍在區塊內 之後再決定
```

# EDGE-7 Indented fence（4 空格，不啟用 fenced block 豁免）

    ```
    Phase 5 再決定 indented
    ```

# EDGE-9 兩個獨立 fenced block 中間空一行

```
Phase 5 再決定 block1
```

```
之後再決定 block2
```

# EDGE-10 inline backtick 行內（不豁免）

這是 inline `Phase 5 再決定` 應仍命中

# EDGE-13 起始 fence 含 language hint 自身行不誤判（AC13）

```javascript
// content
```

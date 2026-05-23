;;; ==============================================================
;;; 仪表属性编号 v5.0.4 - 修复记忆代号格式，行优先，容差可调
;;; 命令：YQBH
;;; ==============================================================
(vl-load-com)

;; ── 用户可调参数 ──────────────────────
(setq *Y-TOL* 50.0)  ; Y 坐标差在此范围内视为同一行

;; ── 工具函数 ──────────────────────────
(defun _parse (s / i)
  (setq i (strlen s))
  (while (and (> i 0) (<= 48 (ascii (substr s i 1)) 57))
    (setq i (1- i)))
  (if (< i (strlen s)) (cons (substr s 1 i) (substr s (1+ i))) nil))

(defun _split (s d / p l)
  (setq d (ascii d))
  (while (setq p (vl-string-position d s))
    (setq l (cons (vl-string-trim " " (substr s 1 p)) l) s (substr s (+ p 2))))
  (reverse (cons (vl-string-trim " " s) l)))

(defun _numstr? (s) (and s (/= s "") (numberp (read s))))

(defun _get-tags (blk / att tags)
  (setq att (entnext blk))
  (while (and att (not (eq "SEQEND" (cdr (assoc 0 (entget att))))))
    (if (= "ATTRIB" (cdr (assoc 0 (entget att))))
      (if (not (member (cdr (assoc 2 (entget att))) tags))
        (setq tags (cons (cdr (assoc 2 (entget att))) tags))))
    (setq att (entnext att)))
  (reverse tags))

(defun _get-att-val (blk tag / att val)
  (setq att (entnext blk))
  (while (and att (not (eq "SEQEND" (cdr (assoc 0 (entget att))))))
    (if (and (= "ATTRIB" (cdr (assoc 0 (entget att))))
             (= (cdr (assoc 2 (entget att))) tag))
      (setq val (cdr (assoc 1 (entget att)))))
    (setq att (entnext att)))
  val)

(defun _get-att-en (blk tag / att en)
  (setq att (entnext blk))
  (while (and att (not (eq "SEQEND" (cdr (assoc 0 (entget att))))))
    (if (and (= "ATTRIB" (cdr (assoc 0 (entget att))))
             (= (cdr (assoc 2 (entget att))) tag))
      (setq en (cdr (assoc -1 (entget att)))))
    (setq att (entnext att)))
  en)

;; ── 记忆文件 ──────────────────────────
(defun _settings-file ()
  (strcat (vl-filename-directory (getvar 'dwgprefix)) "YQBH_Settings.ini"))

(defun _load-settings ( / f line key tag2 codes)
  (setq key nil tag2 nil codes nil)
  (if (setq f (open (_settings-file) "r"))
    (progn
      (while (setq line (read-line f))
        (cond
          ((wcmatch line "TAG1=*") (setq key (substr line 6)))
          ((wcmatch line "TAG2=*") (setq tag2 (substr line 6)))
          ((wcmatch line "CODES=*")
           (setq codes (vl-remove "" (_split (substr line 7) ",")))))
      )
      (close f)
      (if (and key codes) (list key tag2 codes) nil))))

(defun _save-settings (tag1 tag2 codes / f code-str)
  (setq code-str (apply 'strcat (mapcar '(lambda (c) (strcat c ",")) codes)))
  ;; 去除末尾多余的逗号
  (if (and (> (strlen code-str) 0) (= (substr code-str (strlen code-str)) ","))
    (setq code-str (substr code-str 1 (1- (strlen code-str)))))
  (if (setq f (open (_settings-file) "w"))
    (progn
      (write-line (strcat "TAG1=" tag1) f)
      (if tag2 (write-line (strcat "TAG2=" tag2) f))
      (write-line (strcat "CODES=" code-str) f)
      (close f)
      T)
    nil))

;; ── 主命令 ────────────────────────────
(defun c:YQBH ( / *error* ss tag-lst mode tag1 tag2 all-codes sel-codes
                start-str prefix pad is-auto blk-data group-flag groups
                sorted-blks new-num i code ent ins-pt num-enm
                grp-idx grp-ents item token parsed max-num num-str en
                single-code group-reps single-blks pt-a pt-b y-tol
                last-tag1 last-tag2 last-codes last-codes-str)

  (defun *error* (m)
    (if (and m (not (wcmatch m "Function cancelled,quit / exit abort")))
      (princ (strcat "\n错误: " m)))
    (setvar 'cmdecho 1) (princ))

  (setvar 'cmdecho 0)

  ;; 加载记忆
  (setq last ( _load-settings))
  (setq last-tag1 (car last) last-tag2 (cadr last) last-codes (caddr last))

  ;; 1. 选择块
  (prompt "\n选择仪表块（右键结束）...")
  (if (not (setq ss (ssget '((0 . "INSERT") (66 . 1)))))
    (progn (princ "\n未选择块。") (setvar 'cmdecho 1) (quit)))

  ;; 2. 识别属性标签并选择
  (setq tag-lst '() i 0)
  (repeat (sslength ss)
    (foreach tag (_get-tags (ssname ss i))
      (if (not (member tag tag-lst)) (setq tag-lst (cons tag tag-lst))))
    (setq i (1+ i)))
  (setq tag-lst (reverse tag-lst))
  (if (not tag-lst) (progn (princ "\n无属性块。") (quit)))

  (if (= (length tag-lst) 1)
    (progn
      (setq mode 'single tag1 (car tag-lst) tag2 nil)
      (princ (strcat "\n唯一属性标签【" tag1 "】，将直接操作该属性。")))
    (progn
      (setq mode 'dual)
      (princ "\n检测到属性标签：")
      (setq i 1)
      (foreach x tag-lst (princ (strcat "\n  " (itoa i) " - " x)) (setq i (1+ i)))
      ;; 代号标签（带记忆提示）
      (if (and last-tag1 (member last-tag1 tag-lst))
        (progn
          (setq i (1+ (vl-position last-tag1 tag-lst)))
          (princ (strcat "\n选择【仪表代号】标签序号 [上次: " last-tag1 "(" (itoa i) ")] <回车沿用>: "))
          (initget 2) (setq i (getint))
          (if (not i) (setq i (1+ (vl-position last-tag1 tag-lst)))))
        (progn
          (initget 7) (setq i (getint "\n选择【仪表代号】标签序号: "))))
      (setq tag1 (nth (1- i) tag-lst))
      ;; 编号标签（带记忆提示）
      (if (and last-tag2 (member last-tag2 tag-lst))
        (progn
          (setq i (1+ (vl-position last-tag2 tag-lst)))
          (princ (strcat "\n选择【仪表编号】标签序号 [上次: " last-tag2 "(" (itoa i) ")] <回车沿用>: "))
          (initget 2) (setq i (getint))
          (if (not i) (setq i (1+ (vl-position last-tag2 tag-lst)))))
        (progn
          (initget 7) (setq i (getint "\n选择【仪表编号】标签序号: "))))
      (setq tag2 (nth (1- i) tag-lst))
      (if (= tag1 tag2) (progn (princ "\n代号与编号标签不能相同。") (quit))))
    )
  (princ (strcat "\n已选用：代号→" tag1 (if tag2 (strcat "  编号→" tag2) "") "。"))

  ;; 3. 获取要编号的代号列表
  (if (eq mode 'single)
    (progn
      (setq start-str (getstring T "\n输入同类仪表代号（多个用逗号分隔）: "))
      (if (= start-str "") (quit))
      (setq all-codes (mapcar 'strcase (_split start-str ","))))
    (progn
      (setq all-codes '() i 0)
      (repeat (sslength ss)
        (setq ent (ssname ss i))
        (if (setq att-val (_get-att-val ent tag1))
          (if (not (member (strcase att-val) all-codes))
            (setq all-codes (cons (strcase att-val) all-codes))))
        (setq i (1+ i)))
      (setq all-codes (acad_strlsort (reverse all-codes)))
      (if (not all-codes) (progn (princ "\n未提取到任何代号。") (quit)))
      (princ "\n图中现有代号（字母序）：")
      (setq i 1)
      (foreach x all-codes (princ (strcat "\n  " (itoa i) " - " x)) (setq i (1+ i)))
      ;; 支持直接回车使用记忆代号
      (setq last-codes-str (if last-codes (apply 'strcat (mapcar '(lambda (c) (strcat c ",")) last-codes)) ""))
      ;; 去除末尾逗号显示
      (if (and (> (strlen last-codes-str) 0) (= (substr last-codes-str (strlen last-codes-str)) ","))
        (setq last-codes-str (substr last-codes-str 1 (1- (strlen last-codes-str)))))
      (if last-codes
        (progn
          (princ (strcat "\n输入要编号的代号或序号 [上次: " last-codes-str "] <回车沿用>: "))
          (setq start-str (getstring T))
          (if (= start-str "") (setq start-str last-codes-str)))
        (progn
          (setq start-str (getstring T "\n输入要编号的代号或序号（逗号分隔）: "))
          (if (= start-str "") (quit))))
      (setq sel-codes '())
      (foreach token (_split start-str ",")
        (setq token (vl-string-trim " " token))
        (if (and (/= token "") (_numstr? token))
          (progn (setq i (atoi token))
                 (if (or (< i 1) (> i (length all-codes))) (progn (princ "\n序号无效。") (quit)))
                 (setq sel-codes (cons (nth (1- i) all-codes) sel-codes)))
          (progn
            (setq token (strcase token) code nil)
            (foreach x all-codes (if (= token x) (setq code x)))
            (if (not code) (progn (princ (strcat "\n未找到代号 " token)) (quit)))
            (setq sel-codes (cons code sel-codes)))))
      (setq all-codes (reverse sel-codes))))

  ;; ★ 保存当前标签和代号到记忆
  (_save-settings tag1 tag2 all-codes)

  ;; 4. 起始编号与补零
  (setq start-str (getstring T "\n起始编号（如5H001，回车自动顺延纯数字）: "))
  (if (= start-str "")
    (setq prefix "" is-auto T pad 3)
    (progn
      (if (not (setq parsed (_parse start-str))) (progn (princ "\n编号需包含数字部分。") (quit)))
      (setq prefix (car parsed) pad (strlen (cdr parsed)) is-auto nil)
      (initget 6) (setq i (getint (strcat "\n固定数字位数 <" (itoa pad) ">: ")))
      (if i (setq pad i))))
  (if is-auto (progn (initget 6) (setq i (getint "\n固定数字位数（0=不补零）<3>: ")) (if i (setq pad i))))

  ;; 5. 收集块数据 → 关联列表
  (setq blk-data '() i 0)
  (repeat (sslength ss)
    (setq ent (ssname ss i) ins-pt (cdr (assoc 10 (entget ent))) code nil num-enm nil)
    (cond
      ((eq mode 'single)
       (setq code (strcase (_get-att-val ent tag1)))
       (if (and code (member code all-codes))
         (setq num-enm (_get-att-en ent tag1))))
      (t
       (setq code (strcase (_get-att-val ent tag1)))
       (if (and code (member code all-codes))
         (setq num-enm (_get-att-en ent tag2)))))
    (if (and code num-enm ins-pt)
      (setq blk-data (cons (list (cons 'ins-pt ins-pt)
                                 (cons 'num-en num-enm)
                                 (cons 'code code)
                                 (cons 'mode mode)) blk-data)))
    (setq i (1+ i)))
  (if (not blk-data) (progn (princ "\n无匹配的仪表块。") (quit)))

  ;; 6. 分组（可选）
  (initget "Yes No")
  (setq group-flag (getkword "\n是否需要将多个块绑定为相同编号？[是(Y)/否(N)] <N>: "))
  (setq groups '())
  (if (eq group-flag "Yes")
    (progn
      (prompt "\n请框选一组共享编号的仪表（可多次，右键结束分组定义）...")
      (setq grp-idx 1)
      (while (setq grp-ss (ssget '((0 . "INSERT") (66 . 1))))
        (setq grp-ents '() j 0)
        (repeat (sslength grp-ss)
          (setq blk (ssname grp-ss j)
                found-en (_get-att-en blk (if (eq mode 'single) tag1 tag2)))
          (if (and found-en (vl-some '(lambda (b) (equal (cdr (assoc 'num-en b)) found-en)) blk-data))
            (if (not (member found-en grp-ents))
              (setq grp-ents (cons found-en grp-ents))))
          (setq j (1+ j)))
        (if grp-ents
          (progn
            (setq groups (cons (cons grp-idx grp-ents) groups))
            (princ (strcat "\n已记录第 " (itoa grp-idx) " 组（" (itoa (length grp-ents)) " 个块）"))
            (setq grp-idx (1+ grp-idx)))
          (princ "\n所选块不在待编号范围内。"))
        (prompt "\n继续选择下一组（或右键结束）..."))
      (setq groups (reverse groups))
      (if groups (princ (strcat "\n分组定义完成，共 " (itoa (length groups)) " 组。")))))

  ;; 7. ★ 排序：行优先（Y 容差可调），同行内从左到右
  (setq y-tol *Y-TOL*)
  (setq single-blks '()
        group-reps '())
  (foreach b blk-data
    (if (not (vl-some '(lambda (g) (member (cdr (assoc 'num-en b)) (cdr g))) groups))
      (setq single-blks (cons b single-blks))))
  (foreach g groups
    (setq first-en (cadr g)
          ins-pt nil)
    (foreach b blk-data
      (if (equal (cdr (assoc 'num-en b)) first-en)
        (setq ins-pt (cdr (assoc 'ins-pt b)))))
    (if ins-pt
      (setq group-reps (cons (list (cons 'ins-pt ins-pt)
                                   (cons 'group g)
                                   (cons 'type 'group)) group-reps))))
  (setq sorted-blks (append single-blks group-reps))
  (setq sorted-blks
    (vl-sort sorted-blks
      '(lambda (a b)
         (setq pt-a (cdr (assoc 'ins-pt a)) pt-b (cdr (assoc 'ins-pt b)))
         (if (equal (cadr pt-a) (cadr pt-b) y-tol)   ; Y 坐标差 ≤ 容差 → 同一行
           (< (car pt-a) (car pt-b))                 ; 同行从左到右
           (> (cadr pt-a) (cadr pt-b))))))           ; 不同行自上而下

  ;; 8. 计算起始数字
  (if is-auto
    (progn
      (setq max-num 0)
      (foreach item sorted-blks
        (if (assoc 'group item)
          (setq en (cadr (cdr (assoc 'group item)))
                att-val (cdr (assoc 1 (entget en))))
          (setq att-val (cdr (assoc 1 (entget (cdr (assoc 'num-en item)))))))
        (if (and att-val (setq parsed (_parse att-val)))
          (setq num-str (cdr parsed))
          (setq num-str att-val))
        (if (setq num (atoi num-str)) (if (> num max-num) (setq max-num num))))
      (setq new-num (1+ max-num)))
    (setq new-num (atoi (cdr parsed))))

  ;; 9. 写入编号
  (foreach item sorted-blks
    (if (assoc 'group item)
      (progn
        (setq num-str (itoa new-num))
        (while (< (strlen num-str) pad) (setq num-str (strcat "0" num-str)))
        (foreach en (cdr (cdr (assoc 'group item)))
          (setq att-ent (entget en))
          (setq single-code
            (vl-some '(lambda (b) (if (equal (cdr (assoc 'num-en b)) en) (cdr (assoc 'code b)))) blk-data))
          (entmod (subst (cons 1 (if single-code
                                   (strcat single-code (if (eq mode 'single) "-" "") prefix num-str)
                                   (strcat prefix num-str)))
                         (assoc 1 att-ent) att-ent))
          (entupd en))
        (setq new-num (1+ new-num)))
      (progn
        (setq att-ent (entget (cdr (assoc 'num-en item))))
        (setq num-str (itoa new-num))
        (while (< (strlen num-str) pad) (setq num-str (strcat "0" num-str)))
        (setq code (cdr (assoc 'code item)))
        (entmod (subst (cons 1 (if (eq mode 'single)
                                   (strcat code "-" prefix num-str)
                                   (strcat prefix num-str)))
                       (assoc 1 att-ent) att-ent))
        (entupd (cdr (assoc 'num-en item)))
        (setq new-num (1+ new-num)))))

  (princ "\n全部编号完成。")
  (setvar 'cmdecho 1)
  (princ))

(princ "\n仪表编号插件 v5.0.4 已加载，命令：YQBH（记忆修复，容差可调：*Y-TOL*）")
(princ)
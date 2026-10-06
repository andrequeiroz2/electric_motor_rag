# Settings

Referência de `src/eletric_motor/rag/settings.py`. `Settings()` lê a configuração da coleção no Qdrant no momento da construção. A instância fica congelada.

Este arquivo é a descrição do comportamento implementado. Mudou o código, atualize este documento no mesmo passo.

## Bibliotecas

| Peça | Origem | Função neste módulo |
|---|---|---|
| `BaseSettings` | `pydantic-settings` v2 | Lê variáveis do processo e do `.env`, e valida os campos |
| `SettingsConfigDict` | `pydantic-settings` v2 | Configura o modelo: `extra`, `validate_by_name` e `env_file` |
| `Field` | `pydantic` v2 | Default, alias de validação e `ge=1` em `dense_size` |
| `SecretStr` | `pydantic` v2 | Esconde `openai_api_key` de repr e de serialização |
| `frozen=True` | argumento de classe do Pydantic | Recusa atribuição depois da criação |

Não há `os.environ` manual nem `from_env()`. O `SettingsConfigDict` configura `env_file=".env"`: um arquivo `.env` na raiz é lido pelo `python-dotenv` (dependência do `pydantic-settings`). O `.env` está no `.gitignore` — é onde mora a `OPENAI_API_KEY`.

## Arquitetura

```text
Settings()
  argumento do construtor
  variável do processo
  arquivo .env
  valor padrão do campo
  validação do Pydantic
  instância congelada
```

A ordem é essa. Um argumento `Settings(qdrant_url="http://127.0.0.1:6333")` vence a variável `QDRANT_URL`. A variável vence o `.env`, que vence o padrão `http://localhost:6333`. Valor inválido levanta `ValidationError` na construção. Não há default silencioso no lugar de um valor quebrado.

`init_collection` chama `Settings()` sem argumentos. Outro script faz o mesmo importando a classe:

```python
from eletric_motor.rag import Settings

settings = Settings()
```

`from eletric_motor.rag.settings import Settings` entrega a mesma classe. Não existe singleton. Cada `Settings()` lê o ambiente de novo. Duas instâncias não se alteram.

## Constantes do módulo

`DENSE_SIZE` vale `1024`. É a dimensão de `intfloat/multilingual-e5-large` e o default de `dense_size`. Trocar o modelo de embedding exige outra coleção: vetor já gravado com 1024 dimensões não aceita outro tamanho.

`PAYLOAD_INDEXES` é a tupla dos metadados indexados como keyword:

- `source_type`
- `manufacturer`
- `topic`
- `norm_code`
- `language`

Essa tupla não é campo de `Settings`. Nenhuma variável de ambiente a substitui. `_ensure_payload_indexes` percorre esses cinco nomes e cria só o índice que ainda não existe.

## Campos

| Campo | Padrão | Variável de ambiente | Restrição |
|---|---|---|---|
| `qdrant_url` | `http://localhost:6333` | `QDRANT_URL` | string |
| `collection_name` | `eletric_motor` | `QDRANT_COLLECTION` | string |
| `dense_vector_name` | `dense` | `DENSE_VECTOR_NAME` | string |
| `sparse_vector_name` | `sparse` | `SPARSE_VECTOR_NAME` | string |
| `dense_size` | `1024` | `DENSE_SIZE` | inteiro `>= 1` |
| `embedding_threads` | vazio | `EMBEDDING_THREADS` | inteiro `>= 1` |
| `openai_api_key` | vazio | `OPENAI_API_KEY` | `SecretStr`, nunca impressa |
| `llm_model` | `gpt-4o` | `LLM_MODEL` | string |

O nome da variável é o nome do campo, sem prefixo, com maiúsculas e minúsculas ignoradas. `qdrant_url` e `QDRANT_URL` são a mesma variável.

`collection_name` é a exceção. O `validation_alias="QDRANT_COLLECTION"` faz esse campo ler `QDRANT_COLLECTION`. `COLLECTION_NAME` não preenche o campo. `validate_by_name=True` mantém o nome Python no construtor: `Settings(collection_name="motores")` continua válido.

`extra="ignore"` descarta variável desconhecida, como `PATH` ou `UNRELATED`. Ela não entra no modelo e não gera erro.

`dense_size=0` ou negativo levanta `ValidationError` por causa de `ge=1`. String que não é inteiro também falha. O ambiente entrega texto; o Pydantic converte `DENSE_SIZE=1024` para `int` antes de aplicar `ge`.

Uma variável definida e vazia substitui o padrão. `QDRANT_URL=` produz string vazia. `env_ignore_empty` não está ligado.

## Instância congelada

`frozen=True` é recurso do Pydantic, não uma palavra reservada do Python. Depois de criada, a instância recusa atribuição:

```python
settings = Settings()
settings.dense_size = 384  # ValidationError
```

A configuração muda na construção seguinte, por variável ou por argumento. A instância antiga permanece com os valores que tinha.

Quem usa o objeto só lê. `ensure_collection` e `_require_compatible` leem `collection_name`, `dense_vector_name`, `sparse_vector_name` e `dense_size`. `init_collection` lê `qdrant_url` para abrir o `QdrantClient` e para a frase da CLI. `answer_question` lê `openai_api_key` e `llm_model` para montar o `ChatOpenAI`. O trace não grava `qdrant_url` nem a chave: URL pode carregar segredo e `SecretStr` não serializa. Os nomes e o tamanho do vetor entram em `collection.init.started`; o nome do modelo entra em `generate.answered`.

## O que cada campo faz na coleção

`qdrant_url` é o endereço HTTP do Qdrant. O padrão aponta para o serviço local do `compose.yaml`, porta `6333`.

`collection_name` é o nome da coleção criada ou conferida. O padrão atual é `eletric_motor`.

`dense_vector_name` e `sparse_vector_name` são as chaves dos dois vetores na mesma coleção. O denso usa distância cosseno. O esparso usa o modificador IDF do BM25. Esses nomes não estão no ambiente por padrão; `DENSE_VECTOR_NAME` e `SPARSE_VECTOR_NAME` existem porque o `BaseSettings` expõe todo campo.

`dense_size` é o tamanho do vetor denso passado a `VectorParams`. `_require_compatible` recusa coleção já existente com outro tamanho ou outra distância.

## Como acrescentar um campo

1. Declarar o campo em `Settings` com tipo e default. Restrição vai em `Field` por atribuição.
2. Se a variável de ambiente não puder ser o nome do campo em maiúsculas, usar `validation_alias` e manter `validate_by_name=True`.
3. Não colocar segredo em campo que o trace ou a CLI imprimem sem filtro.
4. Atualizar a tabela de campos deste documento no mesmo passo.
5. Consumir o campo lendo a instância. Não reabrir `os.environ` no chamador.

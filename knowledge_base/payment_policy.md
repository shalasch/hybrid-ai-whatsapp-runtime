# Política de Pagamento — Orientações Gerais

Diretrizes sobre como tratar questões financeiras no fluxo automatizado.

## Regra principal

**Questões relacionadas a pagamento, preço ou cobrança devem ser encaminhadas para atendimento humano.**

O sistema automatizado não tem acesso a dados financeiros, planos ativos, histórico de cobranças ou condições contratuais específicas de cada aluno. Qualquer tentativa de resolver questões financeiras automaticamente pode gerar informação incorreta.

## O que se enquadra como questão de pagamento

- Perguntas sobre valor, preço ou mensalidade do curso
- Dúvidas sobre cobranças realizadas ou não realizadas
- Solicitações de parcelamento ou formas de pagamento
- Pedidos de desconto, promoção ou negociação de condições
- Questões sobre boleto, Pix, cartão de crédito
- Solicitações de reembolso, estorno ou cancelamento com devolução de valor
- Dúvidas sobre plano contratado, duração ou renovação

## Comportamento esperado do sistema

Quando qualquer uma das situações acima é identificada:
1. Reconhecer a solicitação do lead/aluno
2. Informar que questões financeiras são atendidas diretamente pela equipe
3. Encaminhar para `human_wait` com `needs_human=true`
4. Não tentar responder sobre valores, prazos ou condições específicas

## Informações que NÃO devem ser dadas automaticamente

- Valores de planos (informação sujeita a mudança e negociação individual)
- Condições de parcelamento (variam por caso)
- Prazos de pagamento (gerenciados administrativamente)
- Status de cobranças (requer acesso ao sistema financeiro)

## Informações gerais que podem ser mencionadas

- O curso tem diferentes planos que podem ser apresentados pela equipe
- O pagamento é feito por canais administrativos (não via WhatsApp bot)
- Questões financeiras são tratadas com sigilo e diretamente com a equipe responsável
